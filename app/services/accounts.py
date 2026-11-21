from datetime import date

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db import SessionLocal, run_migrations
from app.models import (
    AttendanceRecord,
    BenefitRecord,
    EmployeeProfile,
    LeaveBalance,
    User,
)
from app.schemas import EmployeeCreateRequest, EmployeeUpdateRequest, RegisterRequest
from app.services.account_security import hash_password


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "must_change_password": user.must_change_password,
    }


def employee_record(user: User) -> dict:
    profile = user.profile
    leave = profile.leave_balance if profile else None
    return {
        **public_user(user),
        "employee": (
            {
                "employee_id": profile.employee_id,
                "full_name": profile.full_name,
                "job_title": profile.job_title,
                "department": profile.department,
                "location": profile.location,
                "manager": profile.manager,
                "employment_status": profile.employment_status,
                "is_demo": profile.is_demo,
                "leave": (
                    {
                        "annual_leave_days": leave.annual_leave_days,
                        "leave_days_used": leave.leave_days_used,
                        "leave_days_remaining": leave.annual_leave_days
                        - leave.leave_days_used,
                        "as_of": leave.as_of,
                    }
                    if leave
                    else None
                ),
                "attendance": [
                    {
                        "id": row.id,
                        "record_date": row.record_date.isoformat(),
                        "status": row.status,
                        "note": row.note,
                    }
                    for row in sorted(
                        profile.attendance_records,
                        key=lambda item: (item.record_date, item.id),
                        reverse=True,
                    )
                ],
                "benefits": [
                    {
                        "id": row.id,
                        "benefit_name": row.benefit_name,
                        "enrollment_status": row.enrollment_status,
                        "note": row.note,
                    }
                    for row in sorted(profile.benefits, key=lambda item: item.id)
                ],
            }
            if profile
            else None
        ),
    }


def create_employee(
    db: Session,
    data: RegisterRequest | EmployeeCreateRequest,
    *,
    status: str,
    is_demo: bool = False,
    must_change_password: bool = False,
) -> User:
    username = data.email.strip().casefold()
    user = User(
        username=username,
        email=username,
        password_hash=hash_password(data.password),
        role="employee",
        status=status,
        must_change_password=must_change_password,
        profile=EmployeeProfile(
            employee_id=data.employee_id.strip(),
            full_name=data.full_name.strip(),
            job_title=data.job_title.strip(),
            department=data.department.strip(),
            location=data.location.strip(),
            manager=data.manager.strip(),
            is_demo=is_demo,
            leave_balance=LeaveBalance(
                annual_leave_days=getattr(data, "annual_leave_days", 20),
                leave_days_used=getattr(data, "leave_days_used", 0),
                as_of=date.today().isoformat(),
            ),
        ),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with that email or employee ID already exists.",
        ) from exc
    db.refresh(user)
    return user


def find_account(db: Session, identifier: str) -> User | None:
    normalized = identifier.strip().casefold()
    return db.scalar(
        select(User)
        .options(
            joinedload(User.profile)
            .joinedload(EmployeeProfile.leave_balance),
        )
        .outerjoin(EmployeeProfile)
        .where(
            or_(
                User.email == normalized,
                User.username == normalized,
                EmployeeProfile.employee_id == identifier.strip(),
            )
        )
    )


def list_employees(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .options(
                joinedload(User.profile)
                .joinedload(EmployeeProfile.leave_balance),
                joinedload(User.profile)
                .joinedload(EmployeeProfile.attendance_records),
                joinedload(User.profile).joinedload(EmployeeProfile.benefits),
            )
            .where(User.role == "employee")
            .order_by(User.id)
        ).unique()
    )


def list_pending(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .options(joinedload(User.profile))
            .where(User.role == "employee", User.status == "pending")
            .order_by(User.created_at)
        ).unique()
    )


def get_employee(db: Session, user_id: int) -> User:
    user = db.scalar(
        select(User)
        .options(
            joinedload(User.profile).joinedload(EmployeeProfile.leave_balance),
            joinedload(User.profile).joinedload(EmployeeProfile.attendance_records),
            joinedload(User.profile).joinedload(EmployeeProfile.benefits),
        )
        .where(User.id == user_id, User.role == "employee")
    )
    if user is None or user.profile is None:
        raise HTTPException(status_code=404, detail="Employee account not found.")
    return user


def update_employee(
    db: Session, user: User, changes: EmployeeUpdateRequest
) -> User:
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=404, detail="Employee profile not found.")
    values = changes.model_dump(exclude_unset=True)
    email = values.pop("email", None)
    annual_leave_days = values.pop("annual_leave_days", None)
    leave_days_used = values.pop("leave_days_used", None)

    if email is not None:
        user.email = email
        user.username = email
    for field in ("employee_id", "full_name", "job_title", "department", "location", "manager"):
        if field in values and values[field] is not None:
            setattr(profile, field, values[field])

    if annual_leave_days is not None or leave_days_used is not None:
        leave = profile.leave_balance
        if leave is None:
            leave = LeaveBalance(employee_profile_id=profile.id)
            db.add(leave)
            profile.leave_balance = leave
        new_entitlement = (
            annual_leave_days if annual_leave_days is not None else leave.annual_leave_days
        )
        new_used = leave_days_used if leave_days_used is not None else leave.leave_days_used
        if new_used > new_entitlement:
            raise HTTPException(
                status_code=422,
                detail="Used leave days cannot exceed annual leave entitlement.",
            )
        leave.annual_leave_days = new_entitlement
        leave.leave_days_used = new_used
        leave.as_of = date.today().isoformat()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="That email or employee ID is already assigned.",
        ) from exc
    db.refresh(user)
    return get_employee(db, user.id)


def bootstrap_admin(db: Session) -> None:
    settings = get_settings()
    existing = db.scalar(select(User).where(User.role == "admin"))
    if existing is not None:
        return

    email = settings.bootstrap_admin_email.strip().casefold()
    username = (
        settings.bootstrap_admin_username.strip()
        or settings.nexahr_admin_username.strip()
        or (email.split("@", 1)[0] if email else "")
    )
    if not email:
        email = username if "@" in username else f"{username}@nexahr.local"
    password = (
        settings.bootstrap_admin_password
        or settings.nexahr_admin_password
    )
    if not username or not password:
        if settings.app_env.casefold() in {"prod", "production"}:
            raise RuntimeError(
                "Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD "
                "to initialize the first administrator."
            )
        return

    admin = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role="admin",
        status="active",
    )
    db.add(admin)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RuntimeError(
            "Could not bootstrap administrator; the configured email or username "
            "is already assigned to a non-administrator account."
        ) from exc


def seed_demo_employee(db: Session) -> None:
    settings = get_settings()
    if settings.app_env.casefold() in {"prod", "production"}:
        return
    if db.scalar(select(User).where(User.username == "emp1")) is not None:
        return

    user = User(
        username="emp1",
        email="emp1@nexahr.local",
        password_hash=hash_password("emp1-demo"),
        role="employee",
        status="active",
        profile=EmployeeProfile(
            employee_id="EMP-001",
            full_name="Alex Morgan",
            job_title="People Operations Associate",
            department="People Operations",
            location="New York",
            manager="Jordan Lee",
            is_demo=True,
            leave_balance=LeaveBalance(
                annual_leave_days=20,
                leave_days_used=8,
                as_of="2026-10-31",
            ),
        ),
    )
    db.add(user)
    db.commit()


def initialize_account_store() -> None:
    run_migrations()
    db = SessionLocal()
    try:
        bootstrap_admin(db)
        seed_demo_employee(db)
    finally:
        db.close()
