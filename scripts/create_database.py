import asyncio

from asyncpg import DuplicateObjectError, DuplicateTableError
from everbase import compile_table
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.sql.sqltypes import Enum

from core.models.balance import Balance
from core.models.instrument import Instrument
from core.models.order import Order
from core.models.transaction import Transaction
from core.models.user import User
from core.objects.database import database
from core.schemes.user import UserRole


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
            for table in tables:
                await connection.execute(compile_table(table))
        except DuplicateTableError:
            pass

    await database.close()


if __name__ == '__main__':
    asyncio.run(main())
