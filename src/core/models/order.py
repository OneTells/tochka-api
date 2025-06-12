import uuid
from datetime import datetime

from everbase import Base
from sqlalchemy import Integer, Enum, ForeignKey, TIMESTAMP, text, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column as column, MappedColumn as Mapped

from core.models.instrument import Instrument
from core.models.user import User
from core.schemes.order import Direction, OrderStatus


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))

    user_id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    ticker: Mapped[str] = column(Text, ForeignKey(Instrument.ticker, ondelete="CASCADE"), nullable=False)

    direction: Mapped[Direction] = column(Enum(Direction), nullable=False)
    status: Mapped[OrderStatus] = column(
        Enum(OrderStatus),
        nullable=False,
        server_default=text(f"'{OrderStatus.NEW.value}'::orderstatus"),
    )

    qty: Mapped[int] = column(Integer, nullable=False)
    filled: Mapped[int] = column(Integer, nullable=False, server_default=text("0"))

    price: Mapped[int | None] = column(Integer, nullable=True)

    timestamp: Mapped[datetime] = column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
