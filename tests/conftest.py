import pytest
import asyncio
import os

# Set test environment database to SQLite to prevent PostgreSQL dependencies/conflicts during unit testing
os.environ["DATABASE_URL"] = "sqlite:///./test_modernization.db"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session.
    Ensures that SQLAlchemy connection pools and FastAPI clients share a single
    persistent loop lifecycle, avoiding 'RuntimeError: Event loop is closed' warnings.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
