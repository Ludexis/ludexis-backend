import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# The suite drops and recreates every table here, so it must never point at a real database.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://ludexis:ludexis@localhost:5432/ludexis_ci"
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    future=True,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    future=True,
)
