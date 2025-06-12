from typing import Annotated

from everbase import Insert, Select, Delete
from fastapi import APIRouter, Body, Depends, Path, HTTPException
from fastapi.responses import ORJSONResponse
from sqlalchemy import true

from core.methods.authentication import Authentication
from core.middleware.logger import LoggerRoute
from core.models.instrument import Instrument
from core.objects.database import database
from core.schemes.user import UserRole
from modules.instruments.schemes import InstrumentModel
from modules.users.schemes import UserModel

router = APIRouter(route_class=LoggerRoute)


@router.post('/admin/instrument')
async def create_instrument(
    instrument: Annotated[InstrumentModel, Body()],
    _: Annotated[UserModel, Depends(Authentication(user_role=UserRole.ADMIN))]
):
    response = await (
        Insert(Instrument)
        .values(ticker=instrument.ticker, name=instrument.name)
        .on_conflict_do_nothing()
        .returning(true())
        .fetch_all(database)
    )

    if not response:
        raise HTTPException(status_code=409, detail="Инструмент уже существует")

    return ORJSONResponse(content={"success": True})


@router.get('/public/instrument')
async def get_instruments():
    response = await (
        Select(Instrument.ticker, Instrument.name)
        .fetch_all(database, model=lambda x: InstrumentModel(**x).model_dump())
    )

    return ORJSONResponse(content=response)


@router.delete('/admin/instrument/{ticker}')
async def delete_instrument(
    ticker: Annotated[str, Path(pattern='^[A-Z]{2,10}$')],
    _: Annotated[UserModel, Depends(Authentication(user_role=UserRole.ADMIN))]
):
    response = await (
        Delete(Instrument)
        .where(Instrument.ticker == ticker)
        .returning(true())
        .fetch_all(database)
    )

    if not response:
        raise HTTPException(status_code=404, detail="Инструмент не найден")

    return ORJSONResponse(content={"success": True})
