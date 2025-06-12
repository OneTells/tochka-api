import uuid
from typing import Annotated

from everbase import Select, Insert, Update
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
from fastapi.responses import ORJSONResponse
from pydantic import UUID4
from sqlalchemy import true

from core.methods.authentication import Authentication
from core.models.balance import Balance
from core.models.instrument import Instrument
from core.models.order import Order
from core.objects.database import database
from core.schemes.order import Direction, OrderStatus
from core.schemes.user import UserRole
from modules.orders.methods import execute_order
from modules.orders.schemes import LimitOrderBody, MarketOrderBody, LimitOrderModel, MarketOrderModel, OrderBook, Level
from modules.users.schemes import UserModel

router = APIRouter()


@router.post("/order")
async def create_order(
    order: Annotated[LimitOrderBody | MarketOrderBody, Body()],
    user: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    is_instrument_exist = await (
        Select(true())
        .select_from(Instrument)
        .where(Instrument.ticker == order.ticker)
        .fetch_one(database)
    )

    if is_instrument_exist is None:
        raise HTTPException(status_code=404, detail="Инструмент не найден")

    if order.direction == Direction.SELL:
        response = await (
            Select(true())
            .select_from(Balance)
            .where(Balance.user_id == user.id, Balance.ticker == order.ticker, Balance.amount >= order.qty)
            .fetch_one(database)
        )

        if response is None:
            raise HTTPException(status_code=409, detail="Недостаточно средств")
    elif isinstance(order, LimitOrderBody):
        response = await (
            Select(true())
            .select_from(Balance)
            .where(Balance.user_id == user.id, Balance.ticker == 'RUB', Balance.amount >= order.qty * order.price)
            .fetch_one(database)
        )

        if response is None:
            raise HTTPException(status_code=409, detail="Недостаточно средств")

    order_ids: list[uuid.UUID] = await (
        Insert(Order)
        .values(user_id=user.id, ticker=order.ticker, qty=order.qty, price=order.price, direction=order.direction)
        .returning(Order.id)
        .fetch_all(database, model=lambda e: e['id'])
    )

    await execute_order(order_ids[0], order)

    return ORJSONResponse(content={"success": True, 'order_id': order_ids[0]})


@router.get("/order")
async def get_user_orders(
    user: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    response = await (
        Select(Order)
        .where(Order.user_id == user.id, Order.status == OrderStatus.NEW)
        .fetch_all(database)
    )

    result = []

    for order in response:
        if order['price'] is not None:
            result.append(LimitOrderModel(**order, body=LimitOrderBody(**order)).model_dump())
        else:
            result.append(MarketOrderModel(**order, body=MarketOrderBody(**order)).model_dump())

    return ORJSONResponse(content=result)


@router.get("/order/{order_id}")
async def get_order(
    order: Annotated[UUID4, Path()],
    user_id: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    response = await (
        Select(Order)
        .where(Order.user_id == user_id, Order.status == OrderStatus.NEW, Order.id == order.id)
        .fetch_one(database)
    )

    if response['price'] is not None:
        return ORJSONResponse(content=LimitOrderModel(**response, body=LimitOrderBody(**response)).model_dump())

    return ORJSONResponse(content=MarketOrderModel(**response, body=MarketOrderBody(**response)).model_dump())


@router.delete("/order/{order_id}")
async def cancel_order(
    order: Annotated[UUID4, Path()],
    user_id: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    response = await (
        Update(Order)
        .where(Order.user_id == user_id, Order.status == OrderStatus.NEW, Order.id == order.id)
        .values(status=OrderStatus.CANCELLED)
        .returning(true())
        .fetch_all(database)
    )

    if not response:
        raise HTTPException(status_code=409, detail="Ордер нельзя отменить")

    return ORJSONResponse(content={"success": True})


@router.get('/public/orderbook/{ticker}')
async def get_order_book(
    ticker: Annotated[str, Path(pattern='^[A-Z]{2,10}$')],
    limit: Annotated[int, Query(default=10)]
):
    is_instrument_exist = await (
        Select(true())
        .select_from(Instrument)
        .where(Instrument.ticker == ticker)
        .fetch_one(database)
    )

    if is_instrument_exist is None:
        raise HTTPException(status_code=404, detail="Инструмент не найден")

    orders = await (
        Select(Order.price, Order.direction, Order.qty, Order.filled)
        .where(Order.ticker == ticker, Order.status == OrderStatus.NEW)
        .fetch_all(database)
    )

    bids: dict[int, int] = {}
    asks: dict[int, int] = {}

    for order in orders:
        if not order['price']:
            continue

        if order['direction'] == Direction.BUY:
            bids[order['price']] = bids.get(order['price'], 0) + (order['qty'] - order['filled'])
        else:
            asks[order['price']] = asks.get(order['price'], 0) + (order['qty'] - order['filled'])

    return OrderBook(
        bid_levels=[Level(price=price, qty=qty) for price, qty in sorted(bids.items(), reverse=True)[:limit]],
        ask_levels=[Level(price=price, qty=qty) for price, qty in sorted(asks.items())[:limit]]
    )
