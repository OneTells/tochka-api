from typing import Annotated

from asyncpg import Record
from everbase import Select, Insert
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
from fastapi.responses import ORJSONResponse
from pydantic import UUID4
from sqlalchemy import true, func

from core.methods.authentication import Authentication
from core.models.balance import Balance
from core.models.instrument import Instrument
from core.models.order import Order
from core.objects.database import database
from core.schemes.order import Direction, OrderStatus
from core.schemes.user import UserRole
from modules.orders.methods import execute_order
from modules.orders.schemes import LimitOrderBody, MarketOrderBody, LimitOrderModel, MarketOrderModel, OrderBook, Level, \
    OrderModel
from modules.users.schemes import UserModel

router = APIRouter()


@router.post("/order")
async def create_order(
    order: Annotated[LimitOrderBody | MarketOrderBody, Body()],
    user: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    async with database.get_connection() as connection:
        is_instrument_exist = await (
            Select(true())
            .select_from(Instrument)
            .where(Instrument.ticker == order.ticker)
            .fetch_one(connection)
        )

        if is_instrument_exist is None:
            raise HTTPException(status_code=404, detail="Инструмент не найден")

        if order.direction == Direction.SELL:
            balance = await (
                Select(Balance.amount)
                .where(Balance.user_id == user.id, Balance.ticker == order.ticker)
                .fetch_one(connection)
            )

            order_balance: Record = await (
                Select(func.sum(Order.qty - Order.filled).label('amount'))
                .where(
                    Order.direction == Direction.SELL,
                    Order.user_id == user.id,
                    Order.ticker == order.ticker,
                    Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
                )
                .fetch_one(connection)
            )

            available = balance['amount'] - (order_balance['amount'] or 0)
            if available < order.qty:
                raise HTTPException(status_code=409, detail="Недостаточно средств")

        else:
            balance = await (
                Select(Balance.amount)
                .where(Balance.user_id == user.id, Balance.ticker == 'RUB')
                .fetch_one(connection)
            )

            order_balance: Record = await (
                Select(func.sum((Order.qty - Order.filled) * Order.price).label('amount'))
                .where(
                    Order.direction == Direction.BUY,
                    Order.user_id == user.id,
                    Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
                )
                .fetch_one(connection)
            )

            available = balance['amount'] - (order_balance['amount'] or 0)
            if available < order.qty * (order.price if isinstance(order, LimitOrderBody) else 1):
                raise HTTPException(status_code=409, detail="Недостаточно средств")

        orders = await (
            Insert(Order)
            .values(
                user_id=user.id,
                ticker=order.ticker,
                qty=order.qty,
                price=(order.price if isinstance(order, LimitOrderBody) else None),
                direction=order.direction
            )
            .returning(
                Order.id, Order.user_id, Order.price, Order.qty,
                Order.filled, Order.status, Order.direction, Order.ticker
            )
            .fetch_all(connection, model=lambda x: (OrderModel(**x), x['direction'], x['ticker']))
        )

        await execute_order(connection, orders[0][0], orders[0][1], orders[0][2])

    return ORJSONResponse(content={"success": True, 'order_id': orders[0][0].id})


@router.get("/order")
async def get_user_orders(
    user: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    response = await (
        Select(Order)
        .where(Order.user_id == user.id)
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
    order_id: Annotated[UUID4, Path()],
    user: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    response = await (
        Select(Order)
        .where(Order.user_id == user.id, Order.id == order_id)
        .fetch_one(database)
    )

    if response is None:
        raise HTTPException(status_code=404, detail="Ордер не найден")

    if response['price'] is not None:
        return ORJSONResponse(content=LimitOrderModel(**response, body=LimitOrderBody(**response)).model_dump())

    return ORJSONResponse(content=MarketOrderModel(**response, body=MarketOrderBody(**response)).model_dump())


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: Annotated[UUID4, Path()],
    user: Annotated[UserModel, Depends(Authentication(user_role=UserRole.USER))]
):
    order = await (
        Select(Order.id, Order.status, Order.ticker, Order.direction, Order.price, Order.qty)
        .where(
            Order.user_id == user.id,
            Order.id == order_id,
            Order.status.in_([OrderStatus.NEW])
        )
        .fetch_one(database)
    )

    if order is None:
        raise HTTPException(status_code=409, detail="Ордер нельзя отменить")

    return ORJSONResponse(content={"success": True})


@router.get('/public/orderbook/{ticker}')
async def get_order_book(
    ticker: Annotated[str, Path(pattern='^[A-Z]{2,10}$')],
    limit: Annotated[int, Query()] = 10
):
    is_instrument_exist = await (
        Select(true())
        .select_from(Instrument)
        .where(Instrument.ticker == ticker)
        .fetch_one(database)
    )

    if is_instrument_exist is None:
        raise HTTPException(status_code=404, detail="Инструмент не найден")

    bid_orders = await (
        Select(Order.price, func.sum(Order.qty) - func.sum(Order.filled))
        .where(
            Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
            Order.direction == Direction.BUY,
            Order.ticker == ticker,
            Order.price.is_not(None)
        )
        .group_by(Order.price)
        .order_by(Order.price.desc())
        .limit(limit)
        .fetch_all(database)
    )

    ask_orders = await (
        Select(Order.price, func.sum(Order.qty) - func.sum(Order.filled))
        .where(
            Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
            Order.direction == Direction.SELL,
            Order.ticker == ticker,
            Order.price.is_not(None)
        )
        .group_by(Order.price)
        .order_by(Order.price.asc())
        .limit(limit)
        .fetch_all(database)
    )

    return ORJSONResponse(
        content=OrderBook(
            bid_levels=[Level(price=price, qty=qty) for price, qty in bid_orders],
            ask_levels=[Level(price=price, qty=qty) for price, qty in ask_orders]
        ).model_dump()
    )
