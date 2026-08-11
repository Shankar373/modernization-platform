"""Capabilities API — expose the capability registry to the frontend."""
from fastapi import APIRouter

from app.capabilities.registry import registry

router = APIRouter()


@router.get("/capabilities")
async def list_capabilities():
    """Return all registered migration capabilities."""
    return {
        "capabilities": [c.model_dump() for c in registry.get_all()],
        "status_summary": registry.get_status_summary(),
    }


@router.get("/capabilities/{language}")
async def get_capabilities_for_language(language: str):
    """Return capabilities for a specific language."""
    caps = registry.get_for_language(language)
    return {
        "language": language,
        "is_supported": registry.is_language_supported(language),
        "capabilities": [c.model_dump() for c in caps],
    }
