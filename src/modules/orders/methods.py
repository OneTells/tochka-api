import uuid

from everbase import Select, Insert, Update

from core.models.balance import Balance
from core.models.order import Order
from core.models.transaction import Transaction
from core.objects.database import database
from core.schemes.order import Direction, OrderStatus
from modules.orders.schemes import LimitOrderBody, MarketOrderBody


async def deposit(transaction, user_id: uuid.UUID, ticker: str, amount: int):
    await (
        Insert(Balance)
        .values(user_id=user_id, ticker=ticker, amount=amount)
        .on_conflict_do_update(
            index_elements=(Balance.user_id, Balance.ticker), set_={'amount': Balance.amount + amount}
        )
        .execute(transaction)
    )


async def withdraw(transaction, user_id: uuid.UUID, ticker: str, amount: int):
    await (
        Update(Balance)
        .values(amount=Balance.amount - amount)
        .where(Balance.user_id == user_id, Balance.ticker == ticker, Balance.amount >= amount)
        .execute(transaction)
    )


async def execute_order(order_id: uuid.UUID, order: LimitOrderBody | MarketOrderBody):
    whereclause = [
        Order.direction != order.direction,
        Order.ticker == order.ticker,
        Order.status == OrderStatus.NEW
    ]

    order_by = []

    if isinstance(order, LimitOrderBody):
        if order.direction == Direction.BUY:
            whereclause.append(Order.price <= order.price)
        else:
            whereclause.append(Order.price >= order.price)

        order_by.append(Order.price)
    else:
        if order.direction == Direction.BUY:
            order_by.append(Order.price)
        else:
            order_by.append(Order.price.desc())

    opposite_orders = await (
        Select(Order.id, Order.user_id, Order.price, Order.qty, Order.filled)
        .where(*whereclause)
        .order_by(*order_by)
        .fetch(database)
    )

    qty = order.qty
    order_filled = 0

    with database.get_transaction() as transaction:
        for opposite_order in opposite_orders:
            if qty == 0:
                break

            execute_qty = min(qty, opposite_order['qty'] - opposite_order['filled'])

            execute_price = opposite_order['price'] or order.price

            if not execute_price:
                continue

            await (
                Insert(Transaction)
                .values(
                    ticker=order.ticker,
                    amount=execute_qty,
                    price=execute_price,
                    buyer_user_id=order.user_id if order.direction == Direction.BUY else opposite_order['user_id'],
                    seller_user_id=opposite_order['user_id'] if order.direction == Direction.BUY else order.user_id,
                    buyer_order_id=order_id if order.direction == Direction.BUY else opposite_order['id'],
                    seller_order_id=opposite_order['id'] if order.direction == Direction.BUY else order_id
                )
                .execute(transaction)
            )

            if order.direction == Direction.BUY:
                await withdraw(transaction, order.user_id, "RUB", execute_qty * execute_price)
                await deposit(transaction, order.user_id, order.ticker, execute_qty)
                await deposit(transaction, opposite_order['user_id'], "RUB", execute_qty * execute_price)
                await withdraw(transaction, opposite_order['user_id'], order.ticker, execute_qty)
            else:
                await deposit(transaction, order.user_id, "RUB", execute_qty * execute_price)
                await withdraw(transaction, order.user_id, order.ticker, execute_qty)
                await withdraw(transaction, opposite_order['user_id'], "RUB", execute_qty * execute_price)
                await deposit(transaction, opposite_order['user_id'], order.ticker, execute_qty)

        order_filled += execute_qty
        opposite_order['filled'] += execute_qty

        if opposite_order['filled'] == opposite_order['qty']:
            opposite_order.status = OrderStatus.EXECUTED
        else:
            opposite_order.status = OrderStatus.PARTIALLY_EXECUTED

        qty -= execute_qty

        order_status = None

        if qty == 0:
            order_status = OrderStatus.EXECUTED
        elif order_filled > 0:
            order_status = OrderStatus.PARTIALLY_EXECUTED

        if order_status is None:
            return

        await (
            Update(Order)
            .values(status=order_status, filled=order_filled)
            .where(Order.id == order_id)
            .execute(transaction)
        )
