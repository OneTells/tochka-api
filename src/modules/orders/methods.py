import uuid

from everbase import Select, Insert, Update
from everbase.pool import Connection
from pydantic import UUID4

from core.models.balance import Balance
from core.models.order import Order
from core.models.transaction import Transaction
from core.objects.database import database
from core.schemes.order import Direction, OrderStatus
from modules.orders.schemes import LimitOrderBody, OrderModel


async def deposit(transaction: Connection, user_id: UUID4, ticker: str, amount: int):
    await (
        (query := (
            Insert(Balance)
            .values(user_id=user_id, ticker=ticker, amount=amount)
        ))
        .on_conflict_do_update(
            index_elements=(Balance.user_id, Balance.ticker),
            set_={'amount': Balance.amount + query.excluded.amount}
        )
        .execute(transaction)
    )


async def withdraw(transaction, user_id: UUID4, ticker: str, amount: int):
    await (
        Update(Balance)
        .values(amount=Balance.amount - amount)
        .where(Balance.user_id == user_id, Balance.ticker == ticker, Balance.amount >= amount)
        .execute(transaction)
    )


async def execute_order(order: OrderModel, order_direction: Direction, order_ticker: str):
    whereclause = [
        Order.direction != order_direction,
        Order.ticker == order_ticker,
        Order.status == OrderStatus.NEW
    ]

    order_by = []

    if isinstance(order, LimitOrderBody):
        if order_direction == Direction.BUY:
            whereclause.append(Order.price <= order.price)
        else:
            whereclause.append(Order.price >= order.price)

        order_by.append(Order.price)
    else:
        if order_direction == Direction.BUY:
            order_by.append(Order.price)
        else:
            order_by.append(Order.price.desc())

    opposite_orders = await (
        Select(Order.id, Order.user_id, Order.price, Order.qty, Order.filled, Order.status)
        .where(*whereclause)
        .order_by(*order_by)
        .fetch_all(database, model=OrderModel)
    )

    storage: dict[uuid.UUID, OrderModel] = {order.id: order}

    for order_ in opposite_orders:
        storage[order_.id] = order_

    async with database.get_connection() as transaction:
        for opposite_order_ in opposite_orders:
            opposite_order_id = opposite_order_.id

            if storage[order.id].qty - storage[order.id].filled == 0:
                break

            execute_qty = min(
                storage[order.id].qty - storage[order.id].filled,
                storage[opposite_order_id].qty - storage[opposite_order_id].filled
            )
            execute_price = storage[opposite_order_id].price or order.price

            if not execute_price:
                continue

            await (
                Insert(Transaction)
                .values(
                    ticker=order_ticker,
                    amount=execute_qty,
                    price=execute_price,
                    buyer_user_id=order.user_id if order_direction == Direction.BUY else storage[opposite_order_id].user_id,
                    seller_user_id=storage[opposite_order_id].user_id if order_direction == Direction.BUY else order.user_id,
                    buyer_order_id=order.id if order_direction == Direction.BUY else opposite_order_id,
                    seller_order_id=opposite_order_id if order_direction == Direction.BUY else order.id
                )
                .execute(transaction)
            )

            if order_direction == Direction.BUY:
                await withdraw(transaction, order.user_id, "RUB", execute_qty * execute_price)
                await deposit(transaction, order.user_id, order_ticker, execute_qty)
                await deposit(transaction, storage[opposite_order_id].user_id, "RUB", execute_qty * execute_price)
                await withdraw(transaction, storage[opposite_order_id].user_id, order_ticker, execute_qty)
            else:
                await deposit(transaction, order.user_id, "RUB", execute_qty * execute_price)
                await withdraw(transaction, order.user_id, order_ticker, execute_qty)
                await withdraw(transaction, storage[opposite_order_id].user_id, "RUB", execute_qty * execute_price)
                await deposit(transaction, storage[opposite_order_id].user_id, order_ticker, execute_qty)

            storage[order.id].filled += execute_qty
            storage[opposite_order_id].filled += execute_qty

            if storage[opposite_order_id].filled == storage[opposite_order_id].qty:
                storage[opposite_order_id].status = OrderStatus.EXECUTED
            else:
                storage[opposite_order_id].status = OrderStatus.PARTIALLY_EXECUTED

        if storage[order.id].qty == storage[order.id].filled:
            storage[order.id].status = OrderStatus.EXECUTED
        elif storage[order.id].filled > 0:
            storage[order.id].status = OrderStatus.PARTIALLY_EXECUTED

        for order_id, order_ in storage.items():
            if order_.status == OrderStatus.NEW:
                continue

            await (
                Update(Order)
                .values(status=order_.status, filled=order_.filled)
                .where(Order.id == order_.id)
                .execute(transaction)
            )
