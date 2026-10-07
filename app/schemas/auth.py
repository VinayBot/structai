from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_has_digit(cls, value: str) -> str:
        if not any(ch.isdigit() for ch in value):
            raise ValueError("password must contain at least one digit")
        return value


class EmailCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class EmailCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    message: str | None = None
    suggestion: str | None = None
    warning: str | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    role: str


class GithubAuthorizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorize_url: str


class GithubCallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
