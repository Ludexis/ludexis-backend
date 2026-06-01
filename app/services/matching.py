from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.repositories.archive_entry import ArchiveEntryRepository
from app.utils.enums import MetadataStatus


class MatchingService:
    def __init__(self) -> None:
        self.repo = ArchiveEntryRepository()

    def match_title(
        self,
        db: Session,
        title: str,
        version: str | None = None,
    ) -> tuple[str, float | None]:

        exact = self.repo.get_by_title_and_version(
            db,
            title,
            version,
        )

        if exact:
            return "exact", 1.0

        candidates = self.repo.list_titles(db)

        best_match = None
        best_score = 0.0

        for candidate in candidates:
            score = SequenceMatcher(
                None,
                title.lower(),
                candidate.lower(),
            ).ratio()

            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= 0.85:
            return "fuzzy", best_score

        if best_match and best_score >= 0.70:
            return "developer", best_score

        return "manual", best_score

    def metadata_status_for_match(
        self,
        match_type: str,
    ) -> MetadataStatus:
        if match_type == "exact":
            return MetadataStatus.MATCHED

        if match_type in {"fuzzy", "developer"}:
            return MetadataStatus.PARTIAL

        return MetadataStatus.UNMATCHED