from pydantic import BaseModel


class InstrumentModel(BaseModel):
    name: str
    ticker: str
