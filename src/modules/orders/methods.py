import uuid

from asyncpg import Connection
from everbase import Select, Insert, Update
from pydantic import UUID4

from core.models.balance import Balance
from core.models.order import Order
from core.models.transaction import Transaction
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


async def withdraw(transaction: Connection, user_id: UUID4, ticker: str, amount: int):
    await (
        Update(Balance)
        .values(amount=Balance.amount - amount)
        .where(Balance.user_id == user_id, Balance.ticker == ticker, Balance.amount >= amount)
        .execute(transaction)
    )


async def execute_order(connection: Connection, order: OrderModel, order_direction: Direction, order_ticker: str):
    whereclause = [
        Order.direction != order_direction,
        Order.ticker == order_ticker,
        Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
        Order.price.is_not(None)
    ]

    order_by = []

    if order_direction == Direction.BUY:
        if isinstance(order, LimitOrderBody):
            whereclause.append(Order.price <= order.price)

        order_by.append(Order.price.asc())
    else:
        if isinstance(order, LimitOrderBody):
            whereclause.append(Order.price >= order.price)

        order_by.append(Order.price.desc())

    opposite_orders = await (
        Select(Order.id, Order.user_id, Order.price, Order.qty, Order.filled, Order.status)
        .where(*whereclause)
        .order_by(*order_by, Order.timestamp.asc())
        .fetch_all(connection, model=OrderModel)
    )

    storage: dict[uuid.UUID, OrderModel] = {order.id: order}

    for order_ in opposite_orders:
        storage[order_.id] = order_

    try:
        async with connection.transaction():
            user_ids = sorted({order.user_id, *(opp_order.user_id for opp_order in opposite_orders)})

            for user_id in user_ids:
                await connection.execute(
                    "SELECT 1 FROM balances WHERE user_id = $1 AND ticker = 'RUB' FOR UPDATE", user_id
                )

                if order_ticker != 'RUB':
                    await connection.execute(
                        "SELECT 1 FROM balances WHERE user_id = $1 AND ticker = $2 FOR UPDATE",
                        user_id, order_ticker
                    )

            for opposite_order_ in opposite_orders:
                if storage[order.id].qty - storage[order.id].filled == 0:
                    break

                opposite_order_id = opposite_order_.id

                execute_price = storage[opposite_order_id].price

                if not execute_price:
                    raise ValueError("execute_price is None")

                execute_qty = min(
                    storage[order.id].qty - storage[order.id].filled,
                    storage[opposite_order_id].qty - storage[opposite_order_id].filled
                )

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
                    .execute(connection)
                )

                if order_direction == Direction.BUY:
                    await withdraw(connection, order.user_id, "RUB", execute_qty * execute_price)
                    await withdraw(connection, storage[opposite_order_id].user_id, order_ticker, execute_qty)

                    await deposit(connection, order.user_id, order_ticker, execute_qty)
                    await deposit(connection, storage[opposite_order_id].user_id, "RUB", execute_qty * execute_price)
                else:
                    await withdraw(connection, order.user_id, order_ticker, execute_qty)
                    await withdraw(connection, storage[opposite_order_id].user_id, "RUB", execute_qty * execute_price)

                    await deposit(connection, order.user_id, "RUB", execute_qty * execute_price)
                    await deposit(connection, storage[opposite_order_id].user_id, order_ticker, execute_qty)

                storage[order.id].filled += execute_qty
                storage[opposite_order_id].filled += execute_qty

                if storage[opposite_order_id].filled == storage[opposite_order_id].qty:
                    storage[opposite_order_id].status = OrderStatus.EXECUTED
                else:
                    storage[opposite_order_id].status = OrderStatus.PARTIALLY_EXECUTED

            if storage[order.id].qty == storage[order.id].filled:
                storage[order.id].status = OrderStatus.EXECUTED
            elif storage[order.id].filled > 0:
                if not isinstance(order, LimitOrderBody):
                    raise ValueError()

                storage[order.id].status = OrderStatus.PARTIALLY_EXECUTED

            for order_id, order_ in storage.items():
                if order_.status == OrderStatus.NEW:
                    continue

                await (
                    Update(Order)
                    .values(status=order_.status, filled=order_.filled)
                    .where(Order.id == order_.id)
                    .execute(connection)
                )
    except ValueError:
        await (
            Update(Order)
            .values(status=OrderStatus.CANCELLED)
            .where(Order.id == order.id)
            .execute(connection)
        )
