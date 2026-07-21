from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_graph_store
from app.core.config import Settings
from app.core.schemas import HealthResponse
from app.services.graph_store import GraphStore

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: Settings = Depends(get_app_settings),
    store: GraphStore = Depends(get_graph_store),
) -> HealthResponse:
    """Railway liveness/readiness probe (GROUND_RULES 4.2, 12.2)."""
    return HealthResponse(
        status="healthy",
        model_version=settings.MODEL_VERSION,
        gpu_available=False,
        graph_backend="neo4j" if settings.NEO4J_URI else "networkx",
        cases_indexed=store.case_count(),
    )


@router.get("/schema")
async def schema() -> dict:
    """Machine-readable endpoint schema so backend/frontend can auto-generate
    types, per GROUND_RULES 4.2."""
    return {
        "endpoints": {
            "/fuse": {
                "input": {"case_id": "string", "scam_result": "object?", "vision_result": "object?", "user_report": "object?"},
                "output": {
                    "risk_level": "string", "overall_score": "float",
                    "linked_cases": "object[]", "network_analysis": "object",
                    "evidence_package": "object", "recommendations": "object",
                },
            },
            "/graph/query": {
                "input": {"entity_type": "string", "entity_id": "string", "depth": "int"},
                "output": {"nodes": "object[]", "edges": "object[]", "clusters": "object[]"},
            },
            "/evidence/generate": {
                "input": {"case_id": "string", "format": "pdf|json|both"},
                "output": {"pdf_url": "string?", "json_url": "string?", "timeline": "object[]", "appendices": "string[]"},
            },
            "/hotspots": {
                "input": {"state": "string?", "district": "string?", "days": "int?"},
                "output": {"clusters": "object[]", "heatmap_data": "object[]"},
            },
        }
    }
