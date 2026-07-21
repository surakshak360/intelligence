from fastapi import Request

from app.core.config import Settings, get_settings
from app.models.case_registry import CaseRegistry, case_registry
from app.models.job_store import JobStore, job_store
from app.services.graph_store import GraphStore, graph_store


def get_graph_store() -> GraphStore:
    return graph_store


def get_case_registry() -> CaseRegistry:
    return case_registry


def get_job_store() -> JobStore:
    return job_store


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def get_app_settings() -> Settings:
    return get_settings()
