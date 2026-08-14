"""
Capability Registry — YAML-driven, adapter-based.

The registry loads capabilities from YAML catalog files and from registered adapters.
It does NOT contain language-specific if/elif routing.
All language logic lives in the adapters.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from app.core.domain.models import CapabilityStatus, MigrationCapability, RiskLevel


_CATALOG_DIR = Path(__file__).parent / "catalog"

_RISK_MAP = {
    "low": RiskLevel.LOW,
    "medium": RiskLevel.MEDIUM,
    "high": RiskLevel.HIGH,
    "critical": RiskLevel.CRITICAL,
}

_STATUS_MAP = {
    "available": CapabilityStatus.AVAILABLE,
    "partial": CapabilityStatus.PARTIAL,
    "assessment_only": CapabilityStatus.ASSESSMENT_ONLY,
    "not_available": CapabilityStatus.NOT_AVAILABLE,
}


class CapabilityRegistry:
    """
    Central registry of all migration capabilities.

    Capabilities are loaded from YAML catalog files.
    Adapters register their live capabilities at startup.
    The core orchestrator queries this registry — it never
    contains language-specific conditional logic.
    """

    def __init__(self):
        self._capabilities: Dict[str, MigrationCapability] = {}
        self._load_from_catalog()

    def _load_from_catalog(self) -> None:
        """Load capabilities from all YAML files in the catalog directory."""
        if not _CATALOG_DIR.exists():
            return

        for yaml_file in _CATALOG_DIR.rglob("*.yaml"):
            try:
                content = yaml_file.read_text(encoding="utf-8")
                # Handle multi-document YAML (--- separator) and lists
                docs = list(yaml.safe_load_all(content))
                for doc in docs:
                    if not doc:
                        continue
                    # Handle list-style future.yaml
                    if isinstance(doc, list):
                        for entry in doc:
                            self._register_from_dict(entry)
                    elif isinstance(doc, dict):
                        self._register_from_dict(doc)
            except Exception as e:
                print(f"[CapabilityRegistry] Warning: failed to load {yaml_file}: {e}")

    def _register_from_dict(self, entry: dict) -> None:
        if not entry.get("name") or not entry.get("language"):
            return
        status_raw = entry.get("status", "not_available").lower().replace("-", "_")
        risk_raw = entry.get("risk", "medium").lower()

        cap = MigrationCapability(
            name=entry["name"],
            language=entry["language"],
            provider=entry.get("provider", "unknown"),
            status=_STATUS_MAP.get(status_raw, CapabilityStatus.NOT_AVAILABLE),
            source_versions=entry.get("source_versions", []),
            target_versions=entry.get("target_versions", []),
            risk=_RISK_MAP.get(risk_raw, RiskLevel.MEDIUM),
            description=entry.get("description", entry.get("notes", "")),
        )
        self._capabilities[cap.name] = cap

    def register(self, capability: MigrationCapability) -> None:
        """Register a capability (called by adapter at startup)."""
        self._capabilities[capability.name] = capability

    def get_all(self) -> List[MigrationCapability]:
        return list(self._capabilities.values())

    def get_for_language(self, language: str) -> List[MigrationCapability]:
        return [c for c in self._capabilities.values() if c.language.lower() == language.lower()]

    def get_available_for_language(self, language: str) -> List[MigrationCapability]:
        return [
            c for c in self.get_for_language(language)
            if c.status == CapabilityStatus.AVAILABLE
        ]

    def get(self, name: str) -> Optional[MigrationCapability]:
        return self._capabilities.get(name)

    def is_language_supported(self, language: str) -> bool:
        return any(
            c.status in (CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL)
            for c in self.get_for_language(language)
        )

    def get_status_summary(self) -> Dict[str, str]:
        """Return a language → status summary for the UI."""
        summary: Dict[str, str] = {}
        for cap in self._capabilities.values():
            lang = cap.language
            current = summary.get(lang, CapabilityStatus.NOT_AVAILABLE.value)
            # Upgrade status if better capability exists
            priority = {
                CapabilityStatus.AVAILABLE.value: 3,
                CapabilityStatus.PARTIAL.value: 2,
                CapabilityStatus.ASSESSMENT_ONLY.value: 1,
                CapabilityStatus.NOT_AVAILABLE.value: 0,
            }
            if priority.get(cap.status.value, 0) > priority.get(current, 0):
                summary[lang] = cap.status.value
        return summary


# Singleton instance
registry = CapabilityRegistry()
