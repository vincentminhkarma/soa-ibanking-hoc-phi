from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, examples=["minhnguyen"])
    password: str = Field(min_length=6, max_length=128, examples=["123456"])


class UserProfile(BaseModel):
    id: str
    username: str
    full_name: str
    phone: str
    email: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserProfile
