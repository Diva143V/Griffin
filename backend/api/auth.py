from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(user: UserLogin):
    return {
        "status": "success",
        "user": {
            "email": user.email,
            "role": "researcher"
        },
        "token": "jwt-token"
    }
