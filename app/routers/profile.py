from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthAccount
from app.schemas.profile import ProfileCreate, ProfileRead
from app.services.profile_service import create_profile, delete_profile, get_profile, profile_to_context, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/create", response_model=ProfileRead)
def create_user_profile(payload: ProfileCreate, request: Request, db: Session = Depends(get_db)):
    account = db.get(AuthAccount, request.state.account.id)
    if account is None:
        raise HTTPException(status_code=401, detail="请重新登录。")
    if account.profile_id is not None:
        raise HTTPException(status_code=409, detail="当前账号已经创建过学习画像。")
    profile = create_profile(db, payload)
    account.profile_id = profile.id
    db.commit()
    return {"id": profile.id, **{key: value for key, value in profile_to_context(profile).items() if key != "user_id"}}


@router.get("/{user_id}", response_model=ProfileRead)
def read_user_profile(user_id: int, db: Session = Depends(get_db)):
    profile = _require_profile(db, user_id)
    return {"id": profile.id, **{key: value for key, value in profile_to_context(profile).items() if key != "user_id"}}


@router.put("/{user_id}", response_model=ProfileRead)
def replace_user_profile(user_id: int, payload: ProfileCreate, db: Session = Depends(get_db)):
    profile = update_profile(db, _require_profile(db, user_id), payload)
    return {"id": profile.id, **{key: value for key, value in profile_to_context(profile).items() if key != "user_id"}}


@router.delete("/{user_id}")
def remove_user_profile(user_id: int, request: Request, db: Session = Depends(get_db)):
    account = db.get(AuthAccount, request.state.account.id)
    profile = _require_profile(db, user_id)
    if account is not None:
        account.profile_id = None
        db.commit()
    delete_profile(db, profile)
    return {"deleted": True, "user_id": user_id}


def _require_profile(db: Session, user_id: int):
    profile = get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    return profile
