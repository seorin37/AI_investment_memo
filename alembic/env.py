import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 모델을 만들면 여기에 Base.metadata를 연결한다. 지금은 SQL 마이그레이션만 쓴다.
target_metadata = None


def get_url(environ=None) -> str:
    env = os.environ if environ is None else environ
    url = env.get("ALEMBIC_DATABASE_URL") or env.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "ALEMBIC_DATABASE_URL 또는 DATABASE_URL이 없습니다. 환경변수나 .env를 확인하세요."
        )
    return url.strip()


def run_migrations_offline() -> None:
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
