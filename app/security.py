import re
from types import SimpleNamespace

from fastapi import Request
from fastapi.responses import JSONResponse

from app.database import SessionLocal
from app.services.auth_service import csrf_is_valid, find_session


PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/auth/register", "/auth/login", "/auth/status"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _path_user_id(path: str) -> int | None:
    match = re.match(r"^/(?:profile|study-plan|errors|documents)/(\d+)(?:/|$)", path)
    return int(match.group(1)) if match else None


async def enforce_authentication(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)

    with SessionLocal() as db:
        found = find_session(db, request.cookies.get("ielts_session"))
        if found is None:
            return JSONResponse(status_code=401, content={"detail": "请先登录。"})
        session, account = found

        if request.method in UNSAFE_METHODS and not csrf_is_valid(
            session,
            request.cookies.get("ielts_csrf"),
            request.headers.get("X-CSRF-Token"),
        ):
            return JSONResponse(status_code=403, content={"detail": "安全令牌无效，请刷新页面后重试。"})

        claimed_user_id = _path_user_id(path)
        content_type = request.headers.get("content-type", "")
        if claimed_user_id is None and "application/json" in content_type:
            try:
                payload = await request.json()
                value = payload.get("user_id") if isinstance(payload, dict) else None
                claimed_user_id = int(value) if value is not None else None
            except (TypeError, ValueError):
                claimed_user_id = None

        if claimed_user_id is not None and account.profile_id != claimed_user_id:
            return JSONResponse(status_code=403, content={"detail": "无权访问其他用户的数据。"})

        request.state.account = SimpleNamespace(id=account.id, email=account.email, profile_id=account.profile_id)
        request.state.session_id = session.id

    return await call_next(request)
