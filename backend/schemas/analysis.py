from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    codes: list[str] = Field(..., min_length=1, description="A股股票代码列表")


class AnalyzeResponse(BaseModel):
    market: dict
    decisions: list[dict]
    histories: dict[str, list[dict]]
    errors: list[dict]
