from fastapi import APIRouter

from modules.users.api import router as users_router
from modules.instruments.api import router as instruments_router

v1_router = APIRouter(prefix='/v1')
v1_router.include_router(users_router)
v1_router.include_router(instruments_router)
