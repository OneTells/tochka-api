import time
from typing import Callable, Awaitable

from fastapi.routing import APIRoute
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, _StreamingResponse as StreamingResponse
from starlette.requests import Request
from starlette.responses import Response


class LoggerMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[StreamingResponse]]) -> StreamingResponse:
        start_time = time.perf_counter_ns()

        try:
            response = await call_next(request)
        except Exception as error:
            logger.exception(
                f'Ошибка в api: {error}.'
                f'Request({request.method}; {request.url}; headers={request.headers}). '
                f'Время исполнения: {int((time.perf_counter_ns() - start_time) / 1_000_000)} мс'
            )

            raise error

        logger.debug(
            f'Запрос к api. '
            f'Request({request.method}; {request.url}; headers={request.headers}). '
            f'Response({response.status_code}). '
            f'Время исполнения: {int((time.perf_counter_ns() - start_time) / 1_000_000)} мс'
        )

        return response


class LoggerRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            response = await original_route_handler(request)

            logger.info(
                f'Запрос к api. '
                f'Request:'
                f'scope={request.scope}; '
                f'Response:'
                f'status_code={response.status_code}'
                f'body={response.body})'
            )

            return response

        return custom_route_handler
