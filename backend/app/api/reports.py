"""Reports API — list migration reports backed by the database."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import CRUDRepository

router = APIRouter()


@router.get("/reports")
async def list_reports(
    project_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List all persisted migration reports, optionally filtered by project."""
    reports = await CRUDRepository.list_migration_reports(db, project_id=project_id)
    return {
        "count": len(reports),
        "reports": reports,
    }
