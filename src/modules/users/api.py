import uuid
from typing import Annotated

from asyncpg import Record
from everbase import Insert, Select, Delete, Update
from fastapi import APIRouter, Body, Depends, Path, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import UUID4
from sqlalchemy import true, func

from core.methods.authentication import Authentication
from core.models.balance import Balance
from core.models.instrument import Instrument
from core.models.order import Order
from core.models.user import User
from core.objects.database import database
from core.schemes.order import Direction, OrderStatus
from core.schemes.user import UserRole
from modules.users.schemes import UserModel

router = APIRouter()


@router.post('/public/register')
async def create_user(name: Annotated[str, Body(embed=True, min_length=3)]):
    response = await (
        Insert(User)
        .values(name=name, api_key=f'{uuid.uuid4()}')
        .returning(User.id, User.name, User.role, User.api_key)
        .fetch_one(database, model=UserModel)
    )

    return ORJSONResponse(content=response.model_dump())


@router.get('/balance')
async def get_user_balance(user: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]):
    user_balances = await (
        Select(Balance.ticker, Balance.amount)
        .where(Balance.user_id == user.id)
        .fetch_all(database)
    )

    return ORJSONResponse(content={balance['ticker']: balance['amount'] for balance in user_balances})


@router.delete('/admin/user/{user_id}')
async def delete_user(
    user_id: Annotated[UUID4, Path()],
    _: Annotated[UserModel, Depends(Authentication(user_role=UserRole.ADMIN))]
):
    response = await (
        Delete(User)
        .where(User.id == user_id)
        .returning(User.id, User.name, User.role, User.api_key)
        .fetch_one(database, model=UserModel)
    )

    if not response:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return ORJSONResponse(content=response.model_dump())


@router.post("/admin/balance/deposit")
async def deposit(
    user_id: Annotated[UUID4, Body()],
    ticker: Annotated[str, Body(pattern='^[A-Z]{2,10}$')],
    amount: Annotated[int, Body(gt=0)],
    _: Annotated[UserModel, Depends(Authentication(user_role=UserRole.ADMIN))]
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
        (query := (
            Insert(Balance)
            .values(user_id=user_id, ticker=ticker, amount=amount)
        ))
        .on_conflict_do_update(
            index_elements=(Balance.user_id, Balance.ticker),
            set_={'amount': Balance.amount + query.excluded.amount}
        )
        .execute(database)
    )

    return ORJSONResponse(content={"success": True})


@router.post("/admin/balance/withdraw")
async def withdraw(
    user_id: Annotated[UUID4, Body()],
    ticker: Annotated[str, Body(pattern='^[A-Z]{2,10}$')],
    amount: Annotated[int, Body(gt=0)],
    _: Annotated[UserModel, Depends(Authentication(user_role=UserRole.ADMIN))]
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

    balance = await (
        Select(Balance.amount)
        .where(Balance.user_id == user_id, Balance.ticker == ticker)
        .fetch_one(database)
    )

    if balance is None:
        raise HTTPException(status_code=409, detail="Недостаточно средств")

    order_balance: Record = await (
        Select(func.sum(Order.qty - Order.filled).label('amount'))
        .where(
            Order.direction == Direction.SELL,
            Order.user_id == user_id,
            Order.ticker == ticker,
            Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
        )
        .fetch_one(database)
    )

    available = balance['amount'] - (order_balance['amount'] or 0)

    if available < amount:
        raise HTTPException(status_code=409, detail="Недостаточно средств")

    await (
        Update(Balance)
        .values(amount=Balance.amount - amount)
        .where(Balance.user_id == user_id, Balance.ticker == ticker)
        .execute(database)
    )

    return ORJSONResponse(content={"success": True})
