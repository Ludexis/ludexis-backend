from pydantic import BaseModel


class ScanStatus(BaseModel):
    pending: int
    running: int
    success: int
    failed: int
    canceled: int
    total: int
