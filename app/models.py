from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="employee", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    profile: Mapped[EmployeeProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    job_title: Mapped[str] = mapped_column(String(160), default="")
    department: Mapped[str] = mapped_column(String(160), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    manager: Mapped[str] = mapped_column(String(160), default="")
    employment_status: Mapped[str] = mapped_column(String(32), default="active")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="profile")
    leave_balance: Mapped[LeaveBalance | None] = relationship(
        back_populates="profile", uselist=False, cascade="all, delete-orphan"
    )
    attendance_records: Mapped[list[AttendanceRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    benefits: Mapped[list[BenefitRecord]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_profile_id: Mapped[int] = mapped_column(
        ForeignKey("employee_profiles.id"), unique=True, index=True
    )
    annual_leave_days: Mapped[float] = mapped_column(Float, default=20)
    leave_days_used: Mapped[float] = mapped_column(Float, default=0)
    as_of: Mapped[str] = mapped_column(String(32), default="")

    profile: Mapped[EmployeeProfile] = relationship(back_populates="leave_balance")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_profile_id: Mapped[int] = mapped_column(
        ForeignKey("employee_profiles.id"), index=True
    )
    record_date: Mapped[datetime] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")

    profile: Mapped[EmployeeProfile] = relationship(back_populates="attendance_records")


class BenefitRecord(Base):
    __tablename__ = "benefit_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_profile_id: Mapped[int] = mapped_column(
        ForeignKey("employee_profiles.id"), index=True
    )
    benefit_name: Mapped[str] = mapped_column(String(160))
    enrollment_status: Mapped[str] = mapped_column(String(32), default="enrolled")
    note: Mapped[str] = mapped_column(Text, default="")

    profile: Mapped[EmployeeProfile] = relationship(back_populates="benefits")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
