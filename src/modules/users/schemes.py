import uuid

from pydantic import BaseModel

from core.schemes.user import UserRole


class UserModel(BaseModel):
    id: uuid.UUID
    name: str
    role: UserRole
    api_key: str
