from pydantic import BaseModel, UUID4

from core.schemes.user import UserRole


class UserModel(BaseModel):
    id: UUID4
    name: str
    role: UserRole
    api_key: str
