from app.services.metadata import MetadataService


def get_metadata_service() -> MetadataService:
    return MetadataService()
