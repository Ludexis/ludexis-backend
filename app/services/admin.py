from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.collection import Collection
from app.models.developer import Developer
from app.models.franchise import Franchise
from app.models.publisher import Publisher
from app.models.tag import Tag
from app.models.user import User
from app.utils.enums import MetadataStatus, VerificationStatus


class AdminService:
    def _count(self, db: Session, model, active_only: bool = False) -> int:
        query = db.query(model)
        if active_only and hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at.is_(None))
        return query.count()

    def get_stats(self, db: Session) -> dict:
        total_entries = self._count(db, ArchiveEntry, active_only=True)
        matched_metadata = db.query(ArchiveEntry).filter(
            ArchiveEntry.deleted_at.is_(None),
            ArchiveEntry.metadata_status != MetadataStatus.UNMATCHED,
        ).count()
        verified_entries = db.query(ArchiveEntry).filter(
            ArchiveEntry.deleted_at.is_(None),
            ArchiveEntry.verification_status != VerificationStatus.UNKNOWN,
        ).count()
        return {
            "archive_entries": total_entries,
            "collections": self._count(db, Collection, active_only=True),
            "tags": self._count(db, Tag),
            "developers": self._count(db, Developer),
            "publishers": self._count(db, Publisher),
            "franchises": self._count(db, Franchise),
            "users": self._count(db, User, active_only=True),
            "metadata_coverage": round((matched_metadata / total_entries * 100), 2) if total_entries else 0.0,
            "verification_coverage": round((verified_entries / total_entries * 100), 2) if total_entries else 0.0,
        }
