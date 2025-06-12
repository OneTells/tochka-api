from everbase import Base
from sqlalchemy import Text
from sqlalchemy.orm import mapped_column as column, MappedColumn as Mapped


class Instrument(Base):
    __tablename__ = "instruments"

    ticker: Mapped[str] = column(Text, primary_key=True)
    name: Mapped[str] = column(Text, nullable=False)
