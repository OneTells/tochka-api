import time
from typing import Callable, Awaitable

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, _StreamingResponse as StreamingResponse
from starlette.requests import Request

from core.methods.logger import get_real_ip


class LoggerMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[StreamingResponse]]) -> StreamingResponse:
        start_time = time.perf_counter_ns()

        try:
            response = await call_next(request)
        except Exception as error:
            logger.exception(
                f'Ошибка в api: {error}. IP={get_real_ip(request.scope)}. '
                f'Request({request.method}; {request.url}; headers={request.headers}). '
                f'Время исполнения: {int((time.perf_counter_ns() - start_time) / 1_000_000)} мс'
            )

            raise error

        logger.debug(
            f'Запрос к api. IP={get_real_ip(request.scope)}. '
            f'Request({request.method}; {request.url}; headers={request.headers}). '
            f'Response({response.status_code}). '
            f'Время исполнения: {int((time.perf_counter_ns() - start_time) / 1_000_000)} мс'
        )

        return response
