import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from core.schemes.order import Direction


class LimitOrderBody(BaseModel):
    ticker: str
    direction: Direction
    qty: Annotated[int, Field(gt=0)]

    price: Annotated[int, Field(gt=0)]


class MarketOrderBody(BaseModel):
    ticker: str
    direction: Direction
    qty: Annotated[int, Field(gt=0)]


class LimitOrderModel(BaseModel):
    id: uuid.UUID
    status: str
    user_id: uuid.UUID
    timestamp: datetime
    body: LimitOrderBody
    filled: int


class MarketOrderModel(BaseModel):
    id: uuid.UUID
    status: str
    user_id: uuid.UUID
    timestamp: datetime
    body: MarketOrderBody

