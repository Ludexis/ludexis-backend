from typing import Generic, TypeVar

import sqlalchemy as sa
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType]):
        self.model = model

    def create(self, db: Session, obj_in: dict[any, any]) -> ModelType:
        instance = self.model(**obj_in)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    def get(self, db: Session, id: str) -> ModelType | None:
        return db.get(self.model, id)

    def list(self, db: Session, offset: int = 0, limit: int = 100) -> list[ModelType]:
        return db.query(self.model).offset(offset).limit(limit).all()

    def update(self, db: Session, instance: ModelType, obj_in: dict[any, any]) -> ModelType:
        for field, value in obj_in.items():
            setattr(instance, field, value)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    def delete(self, db: Session, instance: ModelType) -> ModelType:
        if hasattr(instance, "deleted_at"):
            instance.deleted_at = sa.func.now()
            db.add(instance)
        else:
            db.delete(instance)
        db.commit()
        return instance
