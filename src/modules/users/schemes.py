from pydantic import BaseModel

from core.schemes.user import UserRole


class UserModel(BaseModel):
    id: str
    name: str
    role: UserRole
    api_key: str
