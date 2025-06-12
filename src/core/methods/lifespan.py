import os
from contextlib import asynccontextmanager
from sys import stderr

from fastapi import FastAPI
from loguru import logger

from core.objects.database import database


class Lifespan:

    @staticmethod
    async def __on_startup():
        logger.remove()

        logger.add(
            stderr, level="INFO",
            backtrace=True, diagnose=True
        )

        os.makedirs('/root/memory/logs', exist_ok=True)

        logger.add(
            f'/root/memory/logs/info.log', level='INFO',
            backtrace=True, diagnose=True, enqueue=True,
            compression='tar.xz', retention='10 days', rotation='100 MB'
        )

        logger.add(
            f'/root/memory/logs/debug.log', level='DEBUG',
            backtrace=True, diagnose=True, enqueue=True,
            compression='tar.xz', retention='10 days', rotation='100 MB'
        )

        await database.connect()
        logger.info('API запушен')

    @staticmethod
    async def __on_shutdown():
        await database.close()

        logger.info('API остановлен')

    @classmethod
    @asynccontextmanager
    async def run(cls, _: FastAPI):
        await cls.__on_startup()
        yield
        await cls.__on_shutdown()
