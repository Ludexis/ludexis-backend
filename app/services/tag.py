from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.repositories.tag import TagRepository
from app.schemas.tag import TagCreate, TagUpdate


class TagService:
    def __init__(self) -> None:
        self.repo = TagRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None) -> list[Tag]:
        tags = self.repo.list_items(db, offset=offset, limit=limit, q=q)
        counts = self.repo.count_entries_for_ids(db, [tag.id for tag in tags])
        for tag in tags:
            tag.entry_count = counts.get(tag.id, 0)
        return tags

    def count(self, db: Session, q: str | None = None) -> int:
        return self.repo.count(db, q=q)

    def get(self, db: Session, tag_id: str) -> Tag | None:
        tag = self.repo.get(db, tag_id)
        if tag is not None:
            tag.entry_count = self.repo.count_entries_for_id(db, tag_id)
        return tag

    def create(self, db: Session, data: TagCreate) -> Tag:
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, tag: Tag, data: TagUpdate) -> Tag:
        return self.repo.update(db, tag, data.model_dump(exclude_none=True))

    def delete(self, db: Session, tag: Tag) -> Tag:
        return self.repo.delete(db, tag)
