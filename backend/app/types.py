from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class JobSummary(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime

class SymbolCount(BaseModel):
    label: str
    count: int

class JobDetail(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime
    symbols: List[str]
    counts: List[SymbolCount]
    mode: Optional[str] = None
    tile_rows: Optional[int] = None
    tile_cols: Optional[int] = None
    input_url: Optional[str] = None
    overlay_url: Optional[str] = None
    error_message: Optional[str] = None
