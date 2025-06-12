from datetime import datetime
from typing import Annotated

from pydantic import Field, BaseModel


class TransactionsModel(BaseModel):
    ticker: Annotated[str, Field(pattern='^[A-Z]{2,10}$')]
    amount: Annotated[int, Field(gt=0)]
    price: Annotated[int, Field(gt=0)]
    timestamp: Annotated[datetime, Field()]
