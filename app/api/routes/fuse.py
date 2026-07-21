import time

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_case_registry, get_graph_store, get_job_store, get_request_id
from app.core.config import Settings
from app.core.schemas import FuseRequest
from app.models.case_registry import CaseRegistry
from app.models.job_store import JobStore
from app.services import evidence, linking, network_analysis, recommendations
from app.services.fusion import fuse_risk, risk_level_for
from app.services.graph_store import GraphStore

router = APIRouter(tags=["fusion"])


@router.post("/fuse")
async def fuse(
    payload: FuseRequest,
    store: GraphStore = Depends(get_graph_store),
    registry: CaseRegistry = Depends(get_case_registry),
    jobs: JobStore = Depends(get_job_store),
    request_id: str = Depends(get_request_id),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    started = time.perf_counter()

    user_report = payload.user_report.model_dump() if payload.user_report else {}

    # 1. Ingest into the graph (creates Case node + links raw indicators).
    store.ingest_case(payload.case_id, payload.scam_result, payload.vision_result, user_report)

    # 2. Deterministic weighted risk fusion (GROUND_RULES 10.2).
    overall_score = round(fuse_risk(payload.scam_result, payload.vision_result, user_report), 4)
    risk_level = risk_level_for(overall_score)
    store.set_case_risk(payload.case_id, overall_score, risk_level)

    # 3. Case linking via shared entities.
    linked_cases = linking.find_linked_cases(store, payload.case_id)

    # 4. Fraud network analysis over the local subgraph.
    net = network_analysis.analyze_network(store, payload.case_id, [c["case_id"] for c in linked_cases])

    # 5. Recommendations (rule engine).
    scam_type = (payload.scam_result or {}).get("scam_type")
    recs = recommendations.build_recommendations(
        risk_level, scam_type, net["pattern"], len(linked_cases), net["central_entities"],
    )

    # 6. Evidence package (PDF + JSON), matching the embedded shape in the
    #    /fuse contract example (GROUND_RULES 6.3).
    raw_inputs = {"scam_result": payload.scam_result, "vision_result": payload.vision_result, "user_report": user_report}
    fuse_result_partial = {
        "case_id": payload.case_id,
        "risk_level": risk_level,
        "overall_score": overall_score,
        "linked_cases": linked_cases,
        "network_analysis": net,
    }
    pkg = evidence.generate_evidence_package(settings, payload.case_id, fuse_result_partial, raw_inputs, "both")

    processing_time_ms = int((time.perf_counter() - started) * 1000)

    result = {
        **fuse_result_partial,
        "evidence_package": {
            "pdf_url": pkg["pdf_url"],
            "json_url": pkg["json_url"],
            "includes": pkg["appendices"],
        },
        "recommendations": recs,
        "processing_time_ms": processing_time_ms,
    }

    registry.save(payload.case_id, result, raw_inputs)

    job_id = jobs.new_id()
    jobs.put_completed(job_id, "/fuse", result)

    return {"job_id": job_id, "status": "completed", "result": result}
