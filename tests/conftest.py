import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.case_registry import case_registry
from app.models.job_store import job_store
from app.services.graph_store import graph_store


@pytest.fixture(autouse=True)
def _reset_state():
    """Each test gets a clean in-memory graph/registry (service is
    process-local state, per the module docstrings)."""
    graph_store._g.clear()
    case_registry._store.clear()
    job_store._jobs.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)
