from typing import List, Optional
from pathlib import Path

from app.validation.models import ValidationResult, ProjectMap, ValidationSummary
from app.validation.workspace_detector import build_project_map
from app.validation.command_resolver import resolve_commands
from app.validation.validator import run_validation
from app.validation.result_classifier import classify_results

class ValidationService:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.project_map: Optional[ProjectMap] = None
        self.baseline_results: List[ValidationResult] = []
        self.modernized_results: List[ValidationResult] = []
        self.optimized_results: List[ValidationResult] = []

    def _get_project_map(self) -> ProjectMap:
        if not self.project_map:
            pm = build_project_map(Path(self.workspace_root))
            self.project_map = resolve_commands(pm)
        return self.project_map

    def run_baseline(self):
        pm = self._get_project_map()
        self.baseline_results = []
        for proj in pm.projects:
            for cmd in proj.build_commands + proj.test_commands:
                res = run_validation(proj, cmd, self.workspace_root)
                self.baseline_results.append(res)
        return self.baseline_results

    def run_modernized(self):
        pm = self._get_project_map()
        self.modernized_results = []
        for proj in pm.projects:
            for cmd in proj.build_commands + proj.test_commands:
                res = run_validation(proj, cmd, self.workspace_root)
                self.modernized_results.append(res)
        return self.modernized_results

    def run_optimized(self):
        pm = self._get_project_map()
        self.optimized_results = []
        for proj in pm.projects:
            for cmd in proj.build_commands + proj.test_commands:
                res = run_validation(proj, cmd, self.workspace_root)
                self.optimized_results.append(res)
        return self.optimized_results

    def get_summary(self) -> ValidationSummary:
        pm = self._get_project_map()
        return classify_results(
            self.baseline_results,
            self.modernized_results,
            self.optimized_results,
            pm
        )
