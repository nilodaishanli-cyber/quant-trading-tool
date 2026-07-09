from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from backend.services.analysis_service import analyze_stock_pool, serialize_analysis
from utils.formatting import parse_stock_codes


router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> dict:
    codes = parse_stock_codes("\n".join(request.codes))
    result = analyze_stock_pool(codes)
    return serialize_analysis(result)
