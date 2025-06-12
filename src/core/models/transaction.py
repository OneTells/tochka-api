import uuid
from datetime import datetime

from everbase import Base
from sqlalchemy import Integer, ForeignKey, text, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column as column, MappedColumn as Mapped

from core.models.instrument import Instrument
from core.models.order import Order
from core.models.user import User


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))

    ticker: Mapped[str] = column(Text, ForeignKey(Instrument.ticker, ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = column(Integer, nullable=False)
    price: Mapped[int] = column(Integer, nullable=False)

    buyer_user_id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    seller_user_id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), ForeignKey(User.id, ondelete="CASCADE"), nullable=False)

    buyer_order_id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), ForeignKey(Order.id, ondelete="CASCADE"), nullable=False)
    seller_order_id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), ForeignKey(Order.id, ondelete="CASCADE"), nullable=False)

    timestamp: Mapped[datetime] = column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
