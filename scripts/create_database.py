import asyncio

from asyncpg import DuplicateObjectError, DuplicateTableError
from everbase import compile_table, Insert

from core.models.balance import Balance
from core.models.instrument import Instrument
from core.models.order import Order
from core.models.transaction import Transaction
from core.models.user import User
from core.objects.database import database


async def main():
    await database.connect()

    tables = [User, Balance, Instrument, Order, Transaction]

    async with database.get_connection() as connection:
        try:
            await connection.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        except DuplicateObjectError:
            pass

        try:
            await connection.execute("CREATE TYPE UserRole AS ENUM('USER', 'ADMIN');")
        except DuplicateObjectError:
            pass

        try:
            await connection.execute("CREATE TYPE Direction AS ENUM('BUY', 'SELL');")
        except DuplicateObjectError:
            pass

        try:
            await connection.execute("CREATE TYPE OrderStatus AS ENUM('NEW', 'EXECUTED', 'PARTIALLY_EXECUTED', 'CANCELLED');")
        except DuplicateObjectError:
            pass

        for table in tables:
            try:
                await connection.execute(compile_table(table))
            except DuplicateTableError:
                pass

        await (
            Insert(Instrument)
            .values(ticker='RUB', name='Российский рубль')
            .on_conflict_do_nothing()
            .fetch_all(connection)
        )

    await database.close()


if __name__ == '__main__':
    asyncio.run(main())
