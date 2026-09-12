import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = os.getenv("postgresql://postgres.hzgcunavogdkrozpbjuk:dearjeahoon0106*@aws-0-ca-central-1.pooler.supabase.com:5432/postgres")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL 환경변수가 설정되지 않았습니다."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()