from asyncpg import Connection, Record
from everbase import Select, Insert, Update
from pydantic import UUID4
from sqlalchemy import func

from core.models.balance import Balance
from core.models.order import Order
from core.models.transaction import Transaction
from core.schemes.order import Direction, OrderStatus
from modules.orders.schemes import LimitOrderBody, OrderModel, MarketOrderBody


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

    try:
        async with connection.transaction():
            for opposite_order in opposite_orders:
                if order.qty - order.filled == 0:
                    break

                execute_price = opposite_order.price

                execute_qty = min(
                    order.qty - order.filled,
                    opposite_order.qty - opposite_order.filled
                )

                if isinstance(order, MarketOrderBody) and order_direction == Direction.BUY:
                    balance = await (
                        Select(Balance.amount)
                        .where(Balance.user_id == order.user_id, Balance.ticker == 'RUB')
                        .fetch_one(connection)
                    )

                    order_balance: Record = await (
                        Select(func.sum((Order.qty - Order.filled) * Order.price).label('amount'))
                        .where(
                            Order.direction == Direction.BUY,
                            Order.user_id == order.user_id,
                            Order.price.is_not(None),
                            Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
                        )
                        .fetch_one(connection)
                    )

                    if balance['amount'] - (order_balance['amount'] or 0) < execute_qty * execute_price:
                        break

                await (
                    Insert(Transaction)
                    .values(
                        ticker=order_ticker,
                        amount=execute_qty,
                        price=execute_price,
                        buyer_user_id=order.user_id if order_direction == Direction.BUY else opposite_order.user_id,
                        seller_user_id=opposite_order.user_id if order_direction == Direction.BUY else order.user_id,
                        buyer_order_id=order.id if order_direction == Direction.BUY else opposite_order.id,
                        seller_order_id=opposite_order.id if order_direction == Direction.BUY else order.id
                    )
                    .execute(connection)
                )

                if order_direction == Direction.BUY:
                    await withdraw(connection, order.user_id, "RUB", execute_qty * execute_price)
                    await withdraw(connection, opposite_order.user_id, order_ticker, execute_qty)

                    await deposit(connection, order.user_id, order_ticker, execute_qty)
                    await deposit(connection, opposite_order.user_id, "RUB", execute_qty * execute_price)
                else:
                    await withdraw(connection, order.user_id, order_ticker, execute_qty)
                    await withdraw(connection, opposite_order.user_id, "RUB", execute_qty * execute_price)

                    await deposit(connection, order.user_id, "RUB", execute_qty * execute_price)
                    await deposit(connection, opposite_order.user_id, order_ticker, execute_qty)

                order.filled += execute_qty
                opposite_order.filled += execute_qty

                if opposite_order.filled == opposite_order.qty:
                    opposite_order.status = OrderStatus.EXECUTED
                else:
                    opposite_order.status = OrderStatus.PARTIALLY_EXECUTED

            if order.qty == order.filled:
                order.status = OrderStatus.EXECUTED
            elif isinstance(order, MarketOrderBody):
                raise ValueError()
            elif order.filled > 0:
                order.status = OrderStatus.PARTIALLY_EXECUTED

            for order_ in opposite_orders + [order]:
                if order_.status not in (OrderStatus.EXECUTED, OrderStatus.PARTIALLY_EXECUTED):
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
