import uuid
from typing import Annotated

from everbase import Select
from fastapi import HTTPException
from fastapi.params import Depends
from fastapi.security import APIKeyHeader

from core.models.user import User
from core.objects.database import database
from core.schemes.user import UserRole
from modules.users.schemes import UserModel

authorization_header = APIKeyHeader(name="authorization")


class Authentication:

    def __init__(self, *, user_role: UserRole):
        self.__user_role = user_role

    @staticmethod
    async def __get_user(authorization: str) -> UserModel:
        try:
            scheme, token = authorization.split(' ', 1)
        except ValueError:
            raise HTTPException(status_code=403, detail="Токен не валиден")

        if scheme.lower() != 'token':
            raise HTTPException(status_code=403, detail="Токен не валиден")

        try:
            uuid.UUID(token)
        except ValueError:
            raise HTTPException(status_code=403, detail="Токен не валиден")

        user = await (
            Select(User.id, User.name, User.role, User.api_key)
            .where(User.api_key == token)
            .fetch_one(database, model=UserModel)
        )

        if user is None:
            raise HTTPException(status_code=403, detail="Токен не валиден")

        return user

    async def __call__(self, authorization: Annotated[str, Depends(authorization_header)]) -> UserModel:
        if authorization is None:
            raise HTTPException(status_code=401, detail="Необходимо авторизоваться")

        user = await self.__get_user(authorization)

        if self.__user_role == UserRole.ADMIN and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Не достаточно прав")

        return user
