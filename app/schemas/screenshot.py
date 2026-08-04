from datetime import datetime

from pydantic import BaseModel


class ScreenshotRead(BaseModel):
    id: str
    archive_entry_id: str
    file_path: str
    caption: str | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
