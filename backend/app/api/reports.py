"""Reports API placeholder."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/reports")
async def list_reports():
    """List all migration reports (placeholder — backed by DB in production)."""
    return {"reports": []}
