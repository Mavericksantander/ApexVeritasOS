from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=128)
    public_key: str = Field(..., min_length=1, max_length=4096)
    expires_in: int | None = Field(default=None, ge=60, le=24 * 60 * 60)


class TokenResponse(BaseModel):
    access_token: str
    expires_in: int

