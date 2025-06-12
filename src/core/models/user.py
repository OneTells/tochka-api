import uuid

from everbase import Base
from sqlalchemy import Enum, text, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column as column, MappedColumn as Mapped

from core.schemes.user import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name: Mapped[str] = column(Text, nullable=False)
    role: Mapped[UserRole] = column(Enum(UserRole), nullable=False, server_default=text(UserRole.USER))
    api_key: Mapped[str] = column(Text, nullable=False, unique=True)
