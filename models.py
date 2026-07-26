from pydantic import BaseModel, Field
from typing import List, Optional

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)
    display_name: str = Field(..., min_length=2, max_length=50)

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    is_online: bool = False

class AuthResponse(BaseModel):
    success: bool
    message: str
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None

class UsersListResponse(BaseModel):
    users: List[UserResponse]
