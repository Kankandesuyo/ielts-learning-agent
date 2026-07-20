from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileCreate(BaseModel):
    current_band: float = Field(..., ge=0, le=9)
    target_band: float = Field(..., ge=0, le=9)
    prep_days: int = Field(..., ge=7, le=365)
    daily_minutes: int = Field(..., ge=15, le=600)
    weak_skills: list[str] = Field(default_factory=list, max_length=4)
    focus_areas: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("weak_skills")
    @classmethod
    def validate_weak_skills(cls, values: list[str]) -> list[str]:
        allowed = {"listening", "speaking", "reading", "writing"}
        cleaned = [value.strip().lower() for value in values if value.strip()]
        invalid = sorted(set(cleaned) - allowed)
        if invalid:
            raise ValueError(f"Unsupported weak skills: {', '.join(invalid)}")
        return list(dict.fromkeys(cleaned))

    @field_validator("focus_areas")
    @classmethod
    def validate_focus_areas(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if any(len(value) > 80 for value in cleaned):
            raise ValueError("Each focus area must be 80 characters or fewer.")
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def validate_score_direction(self):
        if self.target_band < self.current_band:
            raise ValueError("Target band must be greater than or equal to current band.")
        return self


class ProfileRead(ProfileCreate):
    id: int

    model_config = {"from_attributes": True}
