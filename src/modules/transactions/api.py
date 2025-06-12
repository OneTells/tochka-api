from typing import Annotated

from everbase import Select
from fastapi import APIRouter, Query, HTTPException, Path
from sqlalchemy import true


from core.models.instrument import Instrument
from core.models.transaction import Transaction
from core.objects.database import database
from modules.transactions.schemes import TransactionsModel

router = APIRouter()


@router.get("/public/transactions/{ticker}")
async def get_public_transaction(
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

    transactions = await (
        Select(Transaction)
        .where(Transaction.ticker == ticker)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .fetch_all(database, model=TransactionsModel)
    )

    return transactions
