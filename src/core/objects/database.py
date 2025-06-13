from everbase import DatabasePool

from core.config.settings import settings

database = DatabasePool(settings.database, pool_size=1)
