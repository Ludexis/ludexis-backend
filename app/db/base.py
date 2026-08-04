from sqlalchemy import event
from sqlalchemy.orm import declarative_base
from sqlalchemy.schema import DDL

Base = declarative_base()

event.listen(Base.metadata, "before_create", DDL("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
