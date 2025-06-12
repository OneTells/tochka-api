import uuid
from typing import Annotated

from pydantic import BaseModel, UUID4, BeforeValidator, Field

from core.schemes.user import UserRole


class UserModel(BaseModel):
    id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    name: Annotated[str, Field(min_length=3)]
    role: UserRole
    api_key: str
