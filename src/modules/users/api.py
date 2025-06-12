import uuid
from typing import Annotated

from asyncpg import Record
from everbase import Insert, Select, Delete
from fastapi import APIRouter, Body, Depends, Path, HTTPException
from fastapi.responses import ORJSONResponse
from loguru import logger
from sqlalchemy import true, Update

from core.methods.authentication import Authentication
from core.models.balance import Balance
from core.models.instrument import Instrument
from core.models.user import User
from core.objects.database import database
from core.schemes.user import UserRole
from modules.users.schemes import UserModel

router = APIRouter()


@router.post('/public/register')
async def create_user(name: Annotated[str, Body(embed=True)]):
    response: UserModel = await (
        Insert(User)
        .values(name=name, api_key=f'{uuid.uuid4()}')
        .returning(database, User.id, User.name, User.role, User.api_key, model=UserModel)
    )

    return ORJSONResponse(content=response.model_dump())


@router.get('/balance')
async def get_user_balance(user: Annotated[UserModel, Depends(Authentication(is_required=True, user_role=UserRole.USER))]):
    user_balances = await (
        Select(Balance.ticker, Balance.amount)
        .where(Balance.user_id == user.id)
        .fetch(database)
    )

    return ORJSONResponse(content={balance['ticker']: balance['amount'] for balance in user_balances})


@router.delete('/admin/user/{user_id}')
async def delete_user(
    user_id: Annotated[str, Path()],
    _: Annotated[UserModel, Depends(Authentication(is_required=True, user_role=UserRole.ADMIN))]
):
    response: UserModel | None = await (
        Delete(User)
        .where(User.id == user_id)
        .returning(database, User.id, User.name, User.role, User.api_key, model=UserModel)
    )

    if response is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return ORJSONResponse(content=response.model_dump())


@router.post("/balance/deposit")
async def deposit(
    user_id: Annotated[str, Body()],
    ticker: Annotated[str, Body()],
    amount: Annotated[int, Body(min=1)],
    _: Annotated[UserModel, Depends(Authentication(is_required=True, user_role=UserRole.ADMIN))]
):
    is_user_exist = await (
        Select(true())
        .select_from(User)
        .where(User.id == user_id)
        .fetch_one(database)
    )

    if is_user_exist is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    is_instrument_exist = await (
        Select(true())
        .select_from(Instrument)
        .where(Instrument.ticker == ticker)
        .fetch_one(database)
    )

    if is_instrument_exist is None:
        raise HTTPException(status_code=404, detail="Инструмент не найден")

    await (
        Insert(Balance)
        .values(user_id=user_id, ticker=ticker, amount=amount)
        .on_conflict_do_update(index_elements=(Balance.user_id, Balance.ticker), set_={'amount': Balance.amount + amount})
        .execute(database)
    )

    return ORJSONResponse(content={"success": True})


@router.post("/balance/withdraw")
async def withdraw(
    user_id: Annotated[str, Body()],
    ticker: Annotated[str, Body()],
    amount: Annotated[int, Body(min=1)],
    _: Annotated[UserModel, Depends(Authentication(is_required=True, user_role=UserRole.ADMIN))]
):
    is_user_exist = await (
        Select(true())
        .select_from(User)
        .where(User.id == user_id)
        .fetch_one(database)
    )

    if is_user_exist is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    is_instrument_exist = await (
        Select(true())
        .select_from(Instrument)
        .where(Instrument.ticker == ticker)
        .fetch_one(database)
    )

    if is_instrument_exist is None:
        raise HTTPException(status_code=404, detail="Инструмент не найден")

    response = await (
        Update(Balance)
        .values(amount=Balance.amount - amount)
        .where(Balance.user_id == user_id, Balance.ticker == ticker, Balance.amount >= amount)
        .returning(database, true())
    )

    if response is None:
        raise HTTPException(status_code=409, detail="Недостаточно средств")

    return ORJSONResponse(content={"success": True})
