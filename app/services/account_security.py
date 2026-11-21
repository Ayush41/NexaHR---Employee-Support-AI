import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthSession, User

PASSWORD_ITERATIONS = 310_000
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_session(db: Session, user: User, ttl_hours: int) -> str:
    from datetime import datetime, timedelta, timezone

    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.add(
        AuthSession(
            token_digest=digest,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        )
    )
    db.commit()
    return token


def session_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    digest = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    session = db.get(AuthSession, digest)
    if session is None or session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Session is invalid or expired.")

    from datetime import datetime, timezone

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session is invalid or expired.")

    user = db.get(User, session.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Account is not active.")
    return user


def current_user(user: User = Depends(session_user)) -> User:
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail="Change your temporary password before continuing.",
        )
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user
