import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    return email


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=10, max_length=128)
    employee_id: str = Field(min_length=1, max_length=80)
    full_name: str = Field(min_length=1, max_length=160)
    job_title: str = Field(default="", max_length=160)
    department: str = Field(default="", max_length=160)
    location: str = Field(default="", max_length=160)
    manager: str = Field(default="", max_length=160)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank.")
        return value

    @field_validator("employee_id", "full_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required.")
        return cleaned

    @field_validator("job_title", "department", "location", "manager")
    @classmethod
    def strip_optional_text(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def strip_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Enter your email or employee ID.")
        return cleaned

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank.")
        return value


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def reject_blank_new_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank.")
        return value


class EmployeeCreateRequest(RegisterRequest):
    annual_leave_days: float = Field(default=20, ge=0)
    leave_days_used: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_leave_usage(self):
        if self.leave_days_used > self.annual_leave_days:
            raise ValueError("Used leave days cannot exceed annual leave entitlement.")
        return self


class EmployeeUpdateRequest(BaseModel):
    email: str | None = Field(default=None, max_length=254)
    employee_id: str | None = Field(default=None, min_length=1, max_length=80)
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    job_title: str | None = Field(default=None, max_length=160)
    department: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    manager: str | None = Field(default=None, max_length=160)
    annual_leave_days: float | None = Field(default=None, ge=0)
    leave_days_used: float | None = Field(default=None, ge=0)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value is not None else None

    @field_validator("employee_id", "full_name")
    @classmethod
    def validate_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be blank.")
        return cleaned

    @field_validator("job_title", "department", "location", "manager")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_leave_usage(self):
        if self.annual_leave_days is not None and self.leave_days_used is not None:
            if self.leave_days_used > self.annual_leave_days:
                raise ValueError("Used leave days cannot exceed annual leave entitlement.")
        return self


class AttendanceCreateRequest(BaseModel):
    record_date: date
    status: Literal["present", "absent", "remote", "leave"]
    note: str = Field(default="", max_length=1000)


class BenefitCreateRequest(BaseModel):
    benefit_name: str = Field(min_length=1, max_length=160)
    enrollment_status: Literal["enrolled", "eligible", "not_enrolled", "pending"]
    note: str = Field(default="", max_length=1000)

    @field_validator("benefit_name")
    @classmethod
    def validate_benefit_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Benefit name cannot be blank.")
        return cleaned

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        return value.strip()


class AccountSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    status: str
    must_change_password: bool
