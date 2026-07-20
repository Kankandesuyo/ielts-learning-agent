from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.auth import AuthStatus, Credentials
from app.services.auth_service import DuplicateEmailError, authenticate, create_account, create_session, find_session, revoke_session

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, raw_token: str, csrf_token: str) -> None:
    settings = get_settings()
    max_age = settings.session_days * 24 * 60 * 60
    common = {"secure": settings.secure_cookies, "samesite": "strict", "path": "/", "max_age": max_age}
    response.set_cookie("ielts_session", raw_token, httponly=True, **common)
    response.set_cookie("ielts_csrf", csrf_token, httponly=False, **common)


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    common = {"secure": settings.secure_cookies, "samesite": "strict", "path": "/"}
    response.delete_cookie("ielts_session", httponly=True, **common)
    response.delete_cookie("ielts_csrf", httponly=False, **common)


@router.post("/register", response_model=AuthStatus, status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    try:
        account = create_account(db, payload.email, payload.password)
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raw_token, csrf_token, _ = create_session(db, account)
    _set_session_cookies(response, raw_token, csrf_token)
    return {"email": account.email, "profile_id": account.profile_id}


@router.post("/login", response_model=AuthStatus)
def login(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    account = authenticate(db, payload.email, payload.password)
    if account is None:
        raise HTTPException(status_code=401, detail="邮箱或密码错误。")
    raw_token, csrf_token, _ = create_session(db, account)
    _set_session_cookies(response, raw_token, csrf_token)
    return {"email": account.email, "profile_id": account.profile_id}


@router.get("/me", response_model=AuthStatus)
def me(request: Request):
    account = request.state.account
    return {"email": account.email, "profile_id": account.profile_id}


@router.get("/status", response_model=AuthStatus)
def auth_status(request: Request, db: Session = Depends(get_db)):
    found = find_session(db, request.cookies.get("ielts_session"))
    if found is None:
        return {"authenticated": False, "email": None, "profile_id": None}
    _, account = found
    return {"authenticated": True, "email": account.email, "profile_id": account.profile_id}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    revoke_session(db, request.cookies.get("ielts_session"))
    _clear_session_cookies(response)
