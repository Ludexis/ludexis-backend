from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.repositories.tag import TagRepository
from app.schemas.tag import TagCreate, TagUpdate


class TagService:
    def __init__(self) -> None:
        self.repo = TagRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100) -> list[Tag]:
        return self.repo.list_items(db, offset=offset, limit=limit)

    def get(self, db: Session, tag_id: str) -> Tag | None:
        return self.repo.get(db, tag_id)

    def create(self, db: Session, data: TagCreate) -> Tag:
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, tag: Tag, data: TagUpdate) -> Tag:
        return self.repo.update(db, tag, data.model_dump(exclude_none=True))

    def delete(self, db: Session, tag: Tag) -> Tag:
        return self.repo.delete(db, tag)
