import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import router
from app.db import get_db
from app.models import Base, User
from app.services.account_security import hash_password


class AccountApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        self.app = FastAPI()
        self.app.include_router(router)

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        with self.session_factory() as db:
            db.add(
                User(
                    username="admin",
                    email="admin@example.test",
                    password_hash=hash_password("strong-admin-password"),
                    role="admin",
                    status="active",
                )
            )
            db.commit()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()

    def _login(self, identifier: str, password: str) -> tuple[str, dict]:
        response = self.client.post(
            "/api/auth/login",
            json={"identifier": identifier, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        return body["access_token"], body["account"]

    def test_registration_requires_approval_and_employee_role_is_enforced(self) -> None:
        invalid_registration = self.client.post(
            "/api/auth/register",
            json={
                "email": "new.employee@example.test",
                "password": "employee-password-10",
                "employee_id": " ",
                "full_name": " ",
            },
        )
        self.assertEqual(invalid_registration.status_code, 422)

        registration = self.client.post(
            "/api/auth/register",
            json={
                "email": "new.employee@example.test",
                "password": "employee-password-10",
                "employee_id": "EMP-100",
                "full_name": "Avery Employee",
                "job_title": "Analyst",
                "department": "Finance",
                "location": "Remote",
                "manager": "Morgan Manager",
            },
        )
        self.assertEqual(registration.status_code, 202, registration.text)
        user_id = registration.json()["account"]["id"]
        self.assertEqual(registration.json()["account"]["status"], "pending")
        self.assertEqual(registration.json()["account"]["role"], "employee")

        pending_login = self.client.post(
            "/api/auth/login",
            json={
                "identifier": "new.employee@example.test",
                "password": "employee-password-10",
            },
        )
        self.assertEqual(pending_login.status_code, 403)

        admin_token, _ = self._login("admin@example.test", "strong-admin-password")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        approved = self.client.post(
            f"/api/admin/registrations/{user_id}/approve",
            headers=admin_headers,
        )
        self.assertEqual(approved.status_code, 200, approved.text)

        employee_token, account = self._login(
            "EMP-100", "employee-password-10"
        )
        employee_headers = {"Authorization": f"Bearer {employee_token}"}
        self.assertEqual(account["role"], "employee")
        self.assertEqual(
            self.client.get(
                "/api/employee/me", headers=employee_headers
            ).json()["employee"]["department"],
            "Finance",
        )
        self.assertEqual(
            self.client.get(
                "/api/admin/employees", headers=employee_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/admin/employees").status_code,
            401,
        )

        with (
            patch("app.api.routes.ask", side_effect=AssertionError("RAG must not handle personal data")),
            patch("app.api.routes.write_audit"),
        ):
            personal_answer = self.client.post(
                "/api/chat",
                headers=employee_headers,
                json={"question": "What is my department?"},
            )
        self.assertEqual(personal_answer.status_code, 200, personal_answer.text)
        self.assertEqual(personal_answer.json()["source_used"], "employee_records")
        self.assertIn("Finance", personal_answer.json()["answer"])

        leave_questions = (
            "How many leaves do I have left?",
            "How many vacation days do I have?",
            "How much paid time off do I have remaining?",
            "How many days off do I have left?",
        )
        with (
            patch("app.api.routes.ask", side_effect=AssertionError("Leave balance must bypass RAG")),
            patch("app.api.routes.write_audit"),
        ):
            for question in leave_questions:
                leave_answer = self.client.post(
                    "/api/chat",
                    headers=employee_headers,
                    json={"question": question},
                )
                self.assertEqual(leave_answer.status_code, 200, leave_answer.text)
                self.assertEqual(
                    leave_answer.json()["source_used"], "employee_records"
                )
                self.assertIn("20 of 20", leave_answer.json()["answer"])

        with (
            patch(
                "app.api.routes.stream_ask",
                side_effect=AssertionError("Leave balance must bypass RAG"),
            ),
            patch("app.api.routes.write_audit"),
        ):
            streamed_leave = self.client.post(
                "/api/chat/stream",
                headers=employee_headers,
                json={"question": "What's my annual leave balance?"},
            )
        self.assertEqual(streamed_leave.status_code, 200)
        self.assertIn('"source_used": "employee_records"', streamed_leave.text)
        self.assertIn("20 of 20", streamed_leave.text)

        with (
            patch(
                "app.api.routes.ask",
                return_value={
                    "answer": "The company leave policy is available.",
                    "source_used": "private_kb",
                    "trace": [],
                    "citations": [],
                    "current_query": "",
                },
            ),
            patch("app.api.routes.write_audit"),
        ):
            policy_answer = self.client.post(
                "/api/chat",
                headers=employee_headers,
                json={"question": "What is the vacation policy?"},
            )
        self.assertEqual(policy_answer.status_code, 200, policy_answer.text)
        self.assertEqual(policy_answer.json()["source_used"], "private_kb")
    def test_admin_created_account_requires_password_change_and_owns_records(self) -> None:
        admin_token, _ = self._login("admin@example.test", "strong-admin-password")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created = self.client.post(
            "/api/admin/employees",
            headers=admin_headers,
            json={
                "email": "added.employee@example.test",
                "password": "temporary-password-10",
                "employee_id": "EMP-200",
                "full_name": "Jordan Employee",
                "job_title": "Associate",
                "department": "People",
                "location": "HQ",
                "manager": "Taylor Manager",
                "annual_leave_days": 22,
                "leave_days_used": 3,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertTrue(created.json()["must_change_password"])
        user_id = created.json()["id"]

        employee_token, _ = self._login(
            "added.employee@example.test", "temporary-password-10"
        )
        employee_headers = {"Authorization": f"Bearer {employee_token}"}
        self.assertEqual(
            self.client.get(
                "/api/employee/me", headers=employee_headers
            ).status_code,
            403,
        )
        changed = self.client.post(
            "/api/auth/change-password",
            headers=employee_headers,
            json={
                "current_password": "temporary-password-10",
                "new_password": "permanent-password-10",
            },
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        employee_headers = {
            "Authorization": f"Bearer {changed.json()['access_token']}"
        }

        invalid_benefit = self.client.post(
            f"/api/admin/employees/{user_id}/benefits",
            headers=admin_headers,
            json={
                "benefit_name": " ",
                "enrollment_status": "enrolled",
                "note": "",
            },
        )
        self.assertEqual(invalid_benefit.status_code, 422)

        attendance = self.client.post(
            f"/api/admin/employees/{user_id}/attendance",
            headers=admin_headers,
            json={
                "record_date": "2026-11-18",
                "status": "present",
                "note": "On site",
            },
        )
        self.assertEqual(attendance.status_code, 201, attendance.text)
        benefit = self.client.post(
            f"/api/admin/employees/{user_id}/benefits",
            headers=admin_headers,
            json={
                "benefit_name": "Health plan",
                "enrollment_status": "enrolled",
                "note": "",
            },
        )
        self.assertEqual(benefit.status_code, 201, benefit.text)

        own_record = self.client.get(
            "/api/employee/me", headers=employee_headers
        ).json()["employee"]
        self.assertEqual(own_record["leave"]["leave_days_remaining"], 19)
        self.assertEqual(len(own_record["attendance"]), 1)
        self.assertEqual(len(own_record["benefits"]), 1)
        with patch("app.api.routes.write_audit"):
            answer = self.client.post(
                "/api/chat",
                headers=employee_headers,
                json={"question": "What benefits am I enrolled in?"},
            )
        self.assertIn("Health plan", answer.json()["answer"])

        deactivated = self.client.delete(
            f"/api/admin/employees/{user_id}", headers=admin_headers
        )
        self.assertEqual(deactivated.status_code, 200)
        self.assertEqual(
            self.client.get(
                "/api/employee/me", headers=employee_headers
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                f"/api/admin/employees/{user_id}/reactivate",
                headers=admin_headers,
            ).status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
