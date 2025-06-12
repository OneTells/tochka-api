import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, UUID4, BeforeValidator

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
    id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    status: str
    user_id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    timestamp: datetime
    body: LimitOrderBody
    filled: int


class MarketOrderModel(BaseModel):
    id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    status: str
    user_id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    timestamp: datetime
    body: MarketOrderBody

