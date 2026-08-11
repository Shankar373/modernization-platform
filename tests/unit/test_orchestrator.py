import tempfile
from pathlib import Path
from backend.app.core.orchestration.orchestrator import MigrationOrchestrator
from backend.app.core.domain.models import MigrationProfile

def test_orchestrator_flow():
    orchestrator = MigrationOrchestrator()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a Python codebase with styling issues
        Path(tmpdir, "main.py").write_text("import os, sys\n\ndef my_func( ):\n  pass\n")
        Path(tmpdir, "requirements.txt").write_text("pytest\n")
        
        # 1. Scan & Fingerprint
        profile = orchestrator.scan(tmpdir)
        assert any(l.name == "Python" for l in profile.languages)
        
        # 2. Get Assessment
        assessment = orchestrator.get_assessment(tmpdir, profile)
        assert "python" in assessment["supported_languages"]
        
        # 3. Create Plan
        plan = orchestrator.create_plan(tmpdir, profile, "python", "3.11", MigrationProfile.STANDARD)
        assert plan is not None
        assert len(plan.steps) > 0
        
        # 4. Dry Run
        dry_run_res = orchestrator.dry_run(tmpdir, plan)
        assert dry_run_res["success"] is True
        
        # 5. Migrate
        result = orchestrator.migrate(tmpdir, plan)
        assert result.statistics.files_modified > 0
        
        # Check files were modified
        content = Path(tmpdir, "main.py").read_text()
        # Ruff format should clean up spacing
        assert "def my_func():" in content
