import uuid

from everbase import Base
from sqlalchemy import ForeignKey, Integer, Text, text, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column as column, MappedColumn as Mapped

from core.models.instrument import Instrument
from core.models.user import User


class Balance(Base):
    __tablename__ = "balances"

    user_id: Mapped[uuid.UUID] = column(UUID(as_uuid=False), ForeignKey(User.id, ondelete="CASCADE"))
    
    ticker: Mapped[str] = column(Text, ForeignKey(Instrument.ticker, ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = column(Integer, nullable=False, server_default=text("0"))

    # noinspection PyTypeChecker
    __table_args__ = (
        PrimaryKeyConstraint(user_id, ticker, name='user_balances_pk'),
    )
