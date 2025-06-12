from typing import Annotated

from pydantic import BaseModel, Field


class InstrumentModel(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    ticker: Annotated[str, Field(pattern='^[A-Z]{2,10}$')]
