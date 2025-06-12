from datetime import datetime
from typing import Annotated

from fastapi.openapi.models import Schema
from pydantic import Field


class TransactionsModel(Schema):
    ticker: Annotated[str, Field(pattern='^[A-Z]{2,10}$')]
    amount: Annotated[int, Field(gt=0)]
    price: Annotated[int, Field(gt=0)]
    timestamp: Annotated[datetime, Field()]
