import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, UUID4, BeforeValidator

from core.schemes.order import Direction, OrderStatus


class LimitOrderBody(BaseModel):
    ticker: Annotated[str, Field(pattern='^[A-Z]{2,10}$')]
    direction: Direction
    qty: Annotated[int, Field(ge=1)]
    price: Annotated[int, Field(gt=0)]


class MarketOrderBody(BaseModel):
    ticker: Annotated[str, Field(pattern='^[A-Z]{2,10}$')]
    direction: Direction
    qty: Annotated[int, Field(ge=1)]


class LimitOrderModel(BaseModel):
    id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    status: OrderStatus
    user_id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    timestamp: datetime
    body: LimitOrderBody
    filled: Annotated[int, Field(ge=0)]


class MarketOrderModel(BaseModel):
    id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    status: OrderStatus
    user_id: Annotated[UUID4, BeforeValidator(lambda v: uuid.UUID(str(v)))]
    timestamp: datetime
    body: MarketOrderBody


class Level(BaseModel):
    price: Annotated[int, Field(ge=0)]
    qty: Annotated[int, Field(ge=0)]


class OrderBook(BaseModel):
    bid_levels: list[Level]
    ask_levels: list[Level]
