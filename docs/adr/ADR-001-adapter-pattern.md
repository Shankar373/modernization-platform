# ADR-001: Adapter Pattern for Language Migration

**Status:** Accepted  
**Date:** 2026-08-11  
**Deciders:** Platform Architecture Team

## Context

The platform must support migration of applications written in many programming languages.
A naive approach would use `if/elif` chains in the core orchestrator:

```python
# BAD — violates architecture principle
if language == "java":
    run_openrewrite(...)
elif language == "python":
    run_ruff(...)
```

This approach couples the orchestrator to language-specific logic, making it impossible
to add new languages without modifying the core.

## Decision

All language-specific migration logic lives in **adapter classes** that implement
a common `MigrationAdapter` interface:

```python
class MigrationAdapter(ABC):
    def detect(self, workspace_path: str) -> bool: ...
    def analyze(self, profile) -> AnalysisResult: ...
    def get_capabilities(self) -> List[MigrationCapability]: ...
    def create_plan(self, ...) -> MigrationPlan: ...
    def dry_run(self, ...) -> DryRunResult: ...
    def migrate(self, ...) -> MigrationResult: ...
    def validate(self, ...) -> ValidationResult: ...
    def generate_report(self, ...) -> dict: ...
```

The `MigrationOrchestrator` iterates over registered adapters and delegates.
It never contains language-specific conditional logic.

## Consequences

- ✅ New languages can be added without modifying the orchestrator
- ✅ Adapters are independently testable
- ✅ Clear separation of concerns
- ⚠️ Adding a new language requires implementing the full adapter interface
