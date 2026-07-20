import re

from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("请输入有效的邮箱地址。")
        return normalized


class AuthStatus(BaseModel):
    authenticated: bool = True
    email: str | None = None
    profile_id: int | None
