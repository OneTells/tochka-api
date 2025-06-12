from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from core.methods.lifespan import Lifespan
from core.middleware.logger import LoggerMiddleware, LoggerRoute
from general.routers import v1_router

app = FastAPI(
    title='Tochka API',
    version='0.0.1',
    lifespan=Lifespan.run,
    # docs_url=None,
    # redoc_url=None,
    # openapi_url=None,
)

# noinspection PyTypeChecker
app.add_middleware(LoggerMiddleware)

# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

api_router = APIRouter(prefix='/api')
api_router.include_router(v1_router)

app.include_router(api_router)


@app.exception_handler(Exception)
def exception_handler(_: Request, __: Exception):
    return JSONResponse(
        {'detail': "Внутренняя ошибка сервера"}, status_code=HTTP_500_INTERNAL_SERVER_ERROR,
    )


# @app.exception_handler(RequestValidationError)
# def validation_exception_handler(_: Request, __: RequestValidationError):
#     return JSONResponse(
#         {'detail': "Необрабатываемая сущность"}, status_code=HTTP_422_UNPROCESSABLE_ENTITY,
#     )


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('main:app', workers=3, host='0.0.0.0', timeout_keep_alive=600, forwarded_allow_ips="172.19.0.3")
