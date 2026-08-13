"""Real database integration test executing against PostgreSQL if reachable."""
import pytest
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.db.models import DBProject, DBProjectProfile, DBMigrationPlan, DBMigrationRun
from app.db.crud import CRUDRepository
from app.config import settings

# Test Postgres connection details (derived from settings or default fallback)
TEST_PG_URL = settings.database_url
if not TEST_PG_URL.startswith("postgresql"):
    # Fallback to default local Docker compose URL for testing
    TEST_PG_URL = "postgresql+asyncpg://modernize:modernize@localhost:5432/modernization_db"


@pytest.mark.asyncio
async def test_postgres_crud_flow():
    """
    Integration test:
    Connects to PostgreSQL -> Create Project -> Create ProjectProfile
    -> Create MigrationPlan -> Create MigrationRun -> Read back and verify relationships.
    Skips if Postgres is unreachable.
    """
    if not TEST_PG_URL.startswith("postgresql"):
        pytest.skip("PostgreSQL test URL is not configured. Skipping.")

    # 1. Attempt connection
    try:
        engine = create_async_engine(TEST_PG_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Test connection handshake
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as e:
        pytest.skip(f"Local Docker PostgreSQL is not running or unreachable ({e}). Skipping integration test.")
        return

    # 2. Run test CRUD transactions
    async with AsyncSessionLocal() as session:
        try:
            # Generate test IDs
            project_id = str(uuid.uuid4())
            plan_id = str(uuid.uuid4())
            run_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())

            # A. Create Project
            db_proj = await CRUDRepository.create_project(
                db=session,
                project_id=project_id,
                name="test-integration-project",
                source_type="zip",
                source_path="test.zip",
                workspace_path="/tmp/test-workspace",
            )
            assert db_proj.project_id == project_id
            assert db_proj.name == "test-integration-project"

            # B. Create ProjectProfile
            db_profile = await CRUDRepository.create_project_profile(
                db=session,
                project_id=project_id,
                profile_data={
                    "languages": [{"name": "python", "confidence": 1.0}],
                    "frameworks": [{"name": "fastapi", "confidence": 1.0, "language": "python"}],
                    "dependencies": [],
                    "file_count": 10,
                    "total_lines": 1000,
                    "is_multi_language": False,
                }
            )
            assert db_profile.project_id == project_id
            assert len(db_profile.languages) == 1

            # C. Create MigrationPlan
            db_plan = await CRUDRepository.create_migration_plan(
                db=session,
                plan_id=plan_id,
                project_id=project_id,
                profile="STANDARD",
                targets=[{"language": "python", "target_version": "3.11"}],
                steps=[],
                selected_capabilities=["py-ruff-format"],
                overall_risk="LOW",
            )
            assert db_plan.plan_id == plan_id
            assert db_plan.project_id == project_id

            # D. Create MigrationRun
            db_run = await CRUDRepository.create_migration_run(
                db=session,
                result_id=run_id,
                job_id=job_id,
                project_id=project_id,
                plan_id=plan_id,
                status="SUCCESS",
                statistics={"files_modified": 2},
                changed_files=[],
                timeline=[],
                warnings=[],
                manual_remediation=[],
                logs={},
            )
            assert db_run.result_id == run_id
            assert db_run.plan_id == plan_id

            # E. Read records back & Verify relationships
            proj_retrieved = await CRUDRepository.get_project(session, project_id)
            assert proj_retrieved is not None
            assert proj_retrieved.name == "test-integration-project"

            profile_retrieved = await CRUDRepository.get_project_profile(session, project_id)
            assert profile_retrieved is not None
            assert profile_retrieved.languages[0]["name"] == "python"

            run_retrieved = await CRUDRepository.get_migration_run(session, run_id)
            assert run_retrieved is not None
            assert run_retrieved.statistics["files_modified"] == 2

        finally:
            # Rollback transaction so we leave the database clean
            await session.rollback()
            await engine.dispose()
