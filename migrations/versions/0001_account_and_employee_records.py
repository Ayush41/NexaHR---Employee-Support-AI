"""Create account and employee-record tables.

Revision ID: 0001_accounts
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_accounts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.String(length=80), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("job_title", sa.String(length=160), nullable=False),
        sa.Column("department", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("manager", sa.String(length=160), nullable=False),
        sa.Column("employment_status", sa.String(length=32), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("employee_id"),
    )
    op.create_index("ix_employee_profiles_user_id", "employee_profiles", ["user_id"])
    op.create_index("ix_employee_profiles_employee_id", "employee_profiles", ["employee_id"])

    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_profile_id", sa.Integer(), nullable=False),
        sa.Column("annual_leave_days", sa.Float(), nullable=False),
        sa.Column("leave_days_used", sa.Float(), nullable=False),
        sa.Column("as_of", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["employee_profile_id"], ["employee_profiles.id"]),
        sa.UniqueConstraint("employee_profile_id"),
    )
    op.create_index("ix_leave_balances_employee_profile_id", "leave_balances", ["employee_profile_id"])

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_profile_id", sa.Integer(), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["employee_profile_id"], ["employee_profiles.id"]),
    )
    op.create_index(
        "ix_attendance_records_employee_profile_id",
        "attendance_records",
        ["employee_profile_id"],
    )

    op.create_table(
        "benefit_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_profile_id", sa.Integer(), nullable=False),
        sa.Column("benefit_name", sa.String(length=160), nullable=False),
        sa.Column("enrollment_status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["employee_profile_id"], ["employee_profiles.id"]),
    )
    op.create_index("ix_benefit_records_employee_profile_id", "benefit_records", ["employee_profile_id"])

    op.create_table(
        "auth_sessions",
        sa.Column("token_digest", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_benefit_records_employee_profile_id", table_name="benefit_records")
    op.drop_table("benefit_records")
    op.drop_index("ix_attendance_records_employee_profile_id", table_name="attendance_records")
    op.drop_table("attendance_records")
    op.drop_index("ix_leave_balances_employee_profile_id", table_name="leave_balances")
    op.drop_table("leave_balances")
    op.drop_index("ix_employee_profiles_employee_id", table_name="employee_profiles")
    op.drop_index("ix_employee_profiles_user_id", table_name="employee_profiles")
    op.drop_table("employee_profiles")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
