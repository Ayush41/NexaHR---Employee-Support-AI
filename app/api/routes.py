import hashlib
import json
import logging

import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import AttendanceRecord, AuthSession, BenefitRecord, User
from app.rag.vectorstore import add_documents
from app.rag.workflow import ask, stream_ask
from app.schemas import (
    AttendanceCreateRequest,
    BenefitCreateRequest,
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
)
from app.services.account_security import (
    bearer_scheme,
    current_user,
    hash_password,
    issue_session,
    require_admin,
    session_user,
    verify_password,
)
from app.services.accounts import (
    create_employee,
    employee_record,
    find_account,
    get_employee,
    list_employees,
    list_pending,
    public_user,
    update_employee,
)
from app.services.audit import write_audit
from app.services.employee_assistant import answer_personal_question
from app.services.ingestion import SUPPORTED, chunk_documents, load_file

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.post("/auth/register", status_code=202)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = create_employee(db, payload, status="pending")
    return {
        "message": "Registration submitted. An administrator must approve your account.",
        "account": public_user(user),
    }


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = find_account(db, payload.identifier)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")
    if user.status == "pending":
        raise HTTPException(
            status_code=403,
            detail="Your account is awaiting administrator approval.",
        )
    if user.status != "active":
        raise HTTPException(status_code=403, detail="This account is disabled.")

    token = issue_session(db, user, settings.session_ttl_hours)
    return {
        "access_token": token,
        "token_type": "bearer",
        "account": public_user(user),
    }


@router.get("/auth/me")
def who_am_i(user: User = Depends(session_user)):
    return public_user(user)


@router.post("/auth/logout")
def logout(
    user: User = Depends(session_user),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is not None:
        digest = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
        session = db.get(AuthSession, digest)
        if session is not None and session.user_id == user.id:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    return {"message": "Signed out."}


@router.post("/auth/change-password")
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(session_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    now = datetime.now(timezone.utc)
    for session in db.scalars(
        select(AuthSession).where(AuthSession.user_id == user.id)
    ):
        session.revoked_at = now
    db.commit()
    token = issue_session(db, user, settings.session_ttl_hours)
    return {
        "access_token": token,
        "token_type": "bearer",
        "account": public_user(user),
    }


@router.get("/employee/me")
def my_employee_record(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "employee":
        raise HTTPException(status_code=404, detail="Employee profile not found.")
    employee = get_employee(db, user.id)
    return employee_record(employee)


@router.get("/admin/registrations")
def pending_registrations(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    return [employee_record(user) for user in list_pending(db)]


@router.post("/admin/registrations/{user_id}/approve")
def approve_registration(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None or user.role != "employee" or user.status != "pending":
        raise HTTPException(status_code=404, detail="Pending registration not found.")
    user.status = "active"
    db.commit()
    return employee_record(get_employee(db, user.id))


@router.delete("/admin/registrations/{user_id}", status_code=204)
def reject_registration(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None or user.role != "employee" or user.status != "pending":
        raise HTTPException(status_code=404, detail="Pending registration not found.")
    db.delete(user)
    db.commit()


@router.get("/admin/employees")
def employees(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [employee_record(user) for user in list_employees(db)]


@router.post("/admin/employees", status_code=201)
def add_employee(
    payload: EmployeeCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = create_employee(
        db,
        payload,
        status="active",
        must_change_password=True,
    )
    return employee_record(get_employee(db, user.id))


@router.patch("/admin/employees/{user_id}")
def edit_employee(
    user_id: int,
    payload: EmployeeUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    employee = get_employee(db, user_id)
    if employee.status == "disabled":
        raise HTTPException(status_code=409, detail="Reactivate the account before editing it.")
    return employee_record(update_employee(db, employee, payload))


@router.delete("/admin/employees/{user_id}")
def deactivate_employee(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    employee = get_employee(db, user_id)
    employee.status = "disabled"
    if employee.profile:
        employee.profile.employment_status = "inactive"
    for session in db.scalars(
        select(AuthSession).where(AuthSession.user_id == employee.id)
    ):
        session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Employee account deactivated."}


@router.post("/admin/employees/{user_id}/reactivate")
def reactivate_employee(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    employee = get_employee(db, user_id)
    employee.status = "active"
    employee.profile.employment_status = "active"
    db.commit()
    return employee_record(get_employee(db, user_id))


@router.post("/admin/employees/{user_id}/attendance", status_code=201)
def add_attendance_record(
    user_id: int,
    payload: AttendanceCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    employee = get_employee(db, user_id)
    record = AttendanceRecord(
        employee_profile_id=employee.profile.id,
        record_date=payload.record_date,
        status=payload.status,
        note=payload.note.strip(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "record_date": record.record_date.isoformat(),
        "status": record.status,
        "note": record.note,
    }


@router.delete("/admin/employees/{user_id}/attendance/{record_id}", status_code=204)
def delete_attendance_record(
    user_id: int,
    record_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    employee = get_employee(db, user_id)
    record = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.id == record_id,
            AttendanceRecord.employee_profile_id == employee.profile.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
    db.delete(record)
    db.commit()


@router.post("/admin/employees/{user_id}/benefits", status_code=201)
def add_benefit_record(
    user_id: int,
    payload: BenefitCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    employee = get_employee(db, user_id)
    record = BenefitRecord(
        employee_profile_id=employee.profile.id,
        benefit_name=payload.benefit_name,
        enrollment_status=payload.enrollment_status,
        note=payload.note,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "benefit_name": record.benefit_name,
        "enrollment_status": record.enrollment_status,
        "note": record.note,
    }


@router.delete("/admin/employees/{user_id}/benefits/{record_id}", status_code=204)
def delete_benefit_record(
    user_id: int,
    record_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    employee = get_employee(db, user_id)
    record = db.scalar(
        select(BenefitRecord).where(
            BenefitRecord.id == record_id,
            BenefitRecord.employee_profile_id == employee.profile.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Benefit record not found.")
    db.delete(record)
    db.commit()


@router.get("/groq-models")
def check_groq_models(_: User = Depends(require_admin)):
    clean_key = settings.groq_api_key.strip().strip('"').strip("'")
    if not clean_key:
        return {"status": "error", "message": "GROQ_API_KEY is not configured."}
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": "Bearer " + clean_key},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [model["id"] for model in data.get("data", [])]
            return {
                "status": "ok",
                "configured_model": settings.groq_model,
                "available_models_for_your_key": sorted(models),
            }
    except urllib.error.HTTPError as exc:
        return {"status": "error", "code": exc.code, "message": exc.read().decode()}


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)


@router.post("/chat")
def chat(
    payload: ChatRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    personal = (
        answer_personal_question(db, user, payload.question)
        if user.role == "employee"
        else None
    )
    try:
        result = personal or ask(payload.question)
        audit_question = (
            "PERSONAL_EMPLOYEE_DATA_REQUEST" if personal else payload.question
        )
        write_audit(audit_question, result["source_used"], result.get("trace", []))
        return {
            "answer": result["answer"],
            "source_used": result["source_used"],
            "trace": result.get("trace", []),
            "citations": result.get("citations", []),
            "rewritten_query": result.get("current_query", payload.question)
            or payload.question,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat/stream")
def chat_stream(
    payload: ChatRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    personal = (
        answer_personal_question(db, user, payload.question)
        if user.role == "employee"
        else None
    )

    def event_stream():
        try:
            if personal:
                write_audit(
                    "PERSONAL_EMPLOYEE_DATA_REQUEST",
                    personal["source_used"],
                    personal.get("trace", []),
                )
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "step",
                            "node": "employee_records",
                            "data": {"source_used": personal["source_used"], "trace": personal["trace"]},
                        }
                    )
                    + "\n\n"
                )
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "complete",
                            "result": {
                                key: personal[key]
                                for key in (
                                    "answer",
                                    "source_used",
                                    "trace",
                                    "citations",
                                    "current_query",
                                )
                            },
                        }
                    )
                    + "\n\n"
                )
                return

            for event in stream_ask(payload.question):
                if event["type"] == "complete":
                    result = event["result"]
                    write_audit(
                        payload.question,
                        result["source_used"],
                        result.get("trace", []),
                    )
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("Streaming chat request failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"Supported: {', '.join(sorted(SUPPORTED))}",
        )
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / Path(file.filename or "upload").name
    dest.write_bytes(await file.read())
    docs = load_file(dest)
    chunks = chunk_documents(docs)
    ids = add_documents(chunks)
    return {
        "message": "Document indexed",
        "file": dest.name,
        "chunks": len(chunks),
        "ids_created": len(ids),
    }
