import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthAccount, AuthSession
from app.models.tables import utc_now


class DuplicateEmailError(ValueError):
    pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Hash passwords with a random salt and memory-hard scrypt."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(expected_hex)),
        )
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (TypeError, ValueError):
        return False


def create_account(db: Session, email: str, password: str) -> AuthAccount:
    account = AuthAccount(email=email, password_hash=hash_password(password))
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateEmailError("该邮箱已经注册。") from exc
    db.refresh(account)
    return account


def authenticate(db: Session, email: str, password: str) -> AuthAccount | None:
    account = db.scalar(select(AuthAccount).where(AuthAccount.email == email))
    if account is None or not verify_password(password, account.password_hash):
        return None
    return account


def create_session(db: Session, account: AuthAccount) -> tuple[str, str, AuthSession]:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    session = AuthSession(
        account_id=account.id,
        token_hash=_digest(raw_token),
        csrf_hash=_digest(csrf_token),
        expires_at=utc_now() + timedelta(days=settings.session_days),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw_token, csrf_token, session


def find_session(db: Session, raw_token: str | None) -> tuple[AuthSession, AuthAccount] | None:
    if not raw_token:
        return None
    now = utc_now()
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    db.commit()
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _digest(raw_token)))
    if session is None or session.expires_at <= now:
        return None
    account = db.get(AuthAccount, session.account_id)
    return (session, account) if account is not None else None


def csrf_is_valid(session: AuthSession, cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        return False
    return hmac.compare_digest(session.csrf_hash, _digest(header_token))


def revoke_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    db.execute(delete(AuthSession).where(AuthSession.token_hash == _digest(raw_token)))
    db.commit()
