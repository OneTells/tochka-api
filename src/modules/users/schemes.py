import uuid
from typing import Annotated

from pydantic import BaseModel, UUID4, BeforeValidator

from core.schemes.user import UserRole


class UserModel(BaseModel):
    id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    name: str
    role: UserRole
    api_key: str
