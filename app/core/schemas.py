"""
Pydantic I/O schemas for the intelligence service.

Shapes are taken directly from GROUND_RULES.md:
  - section 6.3  intelligence (Port 8000) endpoint contracts
  - section 5.2  Neo4j graph schema (node/edge vocabulary)
  - section 2.2/2.4  response envelope + pagination

Upstream ML outputs (scam_result / vision_result) come from the
scam-intelligence and vision services and are treated as loosely-typed
dicts here (`extra="allow"`) — this service does not own those schemas,
it only consumes the fields it needs (risk_score, entities, ...), per
GROUND_RULES 4.3 ("ML service assumes valid input").
"""
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Shared envelope helpers (section 2.2 / 2.4)
# ---------------------------------------------------------------------------


def success_envelope(data: Any, request_id: str, **meta_extra: Any) -> dict:
    return {
        "success": True,
        "data": data,
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "version": "1.0.0",
            **meta_extra,
        },
    }


# ---------------------------------------------------------------------------
# /health, /schema (section 4.2 — standard ML service interface)
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    status: Literal["healthy", "degraded", "unhealthy"]
    model_version: str
    gpu_available: bool = False
    graph_backend: Literal["networkx", "neo4j"]
    cases_indexed: int


# ---------------------------------------------------------------------------
# POST /fuse  (section 6.3)
# ---------------------------------------------------------------------------


class UserReport(BaseModel):
    reporter_id: Optional[str] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    case_type: Optional[str] = Field(
        default=None, description="digital_arrest | counterfeit | phishing | other"
    )
    location: Optional[dict] = Field(
        default=None, description='GeoJSON Point, e.g. {"lat": 28.61, "lng": 77.20}'
    )

    model_config = {"extra": "allow"}


class FuseRequest(BaseModel):
    case_id: str = Field(..., min_length=1)
    scam_result: Optional[dict] = None
    vision_result: Optional[dict] = None
    user_report: Optional[UserReport] = None

    @field_validator("case_id")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("case_id must not be blank")
        return v.strip()

    model_config = {"extra": "allow"}


class LinkedCase(BaseModel):
    case_id: str
    similarity: float
    shared_entities: list[str]


class NetworkAnalysis(BaseModel):
    cluster_id: Optional[str] = None
    size: int
    central_entities: list[str]
    pattern: str
    jurisdictions: list[str]


class EvidencePackageRef(BaseModel):
    pdf_url: str
    json_url: str
    includes: list[str]


class Recommendations(BaseModel):
    citizen: list[str]
    officer: list[str]
    analyst: list[str]


class FuseResult(BaseModel):
    case_id: str
    risk_level: Literal["low", "medium", "high", "critical"]
    overall_score: float
    linked_cases: list[LinkedCase]
    network_analysis: NetworkAnalysis
    evidence_package: EvidencePackageRef
    recommendations: Recommendations
    processing_time_ms: int


# ---------------------------------------------------------------------------
# POST /graph/query  (section 6.3)
# ---------------------------------------------------------------------------


class GraphQueryRequest(BaseModel):
    entity_type: str = Field(..., description="Person|Account|Device|PhoneNumber|IPAddress|Case|Location")
    entity_id: str
    depth: int = Field(default=1, ge=1, le=4)


class GraphNode(BaseModel):
    id: str
    label: str
    properties: dict


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: dict = {}


class GraphCluster(BaseModel):
    cluster_id: str
    node_ids: list[str]
    size: int


class GraphQueryResult(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    clusters: list[GraphCluster]


# ---------------------------------------------------------------------------
# POST /evidence/generate  (section 6.3, 10.3)
# ---------------------------------------------------------------------------


class EvidenceGenerateRequest(BaseModel):
    case_id: str
    format: Literal["pdf", "json", "both"] = "both"


class TimelineEntry(BaseModel):
    timestamp: str
    event: str


class EvidenceGenerateResult(BaseModel):
    pdf_url: Optional[str] = None
    json_url: Optional[str] = None
    timeline: list[TimelineEntry]
    appendices: list[str]


# ---------------------------------------------------------------------------
# GET /hotspots  (section 6.3)
# ---------------------------------------------------------------------------


class HotspotCluster(BaseModel):
    cluster_id: str
    center: dict  # {"lat": .., "lng": ..}
    radius_km: float
    case_count: int
    dominant_type: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None


class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    weight: float = 1.0


class HotspotsResult(BaseModel):
    clusters: list[HotspotCluster]
    heatmap_data: list[HeatmapPoint]
