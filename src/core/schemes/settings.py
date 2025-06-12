from everbase import DatabaseSettings
from pydantic_settings import BaseSettings, SettingsConfigDict


print(open('.env').read())

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_nested_delimiter='__')

    database: DatabaseSettings
