from pydantic import BaseModel


class GenreRead(BaseModel):
    name: str
    entry_count: int
