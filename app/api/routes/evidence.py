from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_case_registry
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.schemas import EvidenceGenerateRequest
from app.models.case_registry import CaseRegistry
from app.services import evidence

router = APIRouter(tags=["evidence"])


@router.post("/evidence/generate")
async def evidence_generate(
    payload: EvidenceGenerateRequest,
    registry: CaseRegistry = Depends(get_case_registry),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    entry = registry.get(payload.case_id)
    if not entry:
        raise NotFoundError(
            f"No fused case '{payload.case_id}'. Call POST /fuse first.",
            {"case_id": payload.case_id},
        )

    pkg = evidence.generate_evidence_package(
        settings, payload.case_id, entry["fuse_result"], entry["raw_inputs"], payload.format,
    )

    return {
        "job_id": None,
        "status": "completed",
        "result": {
            "pdf_url": pkg["pdf_url"],
            "json_url": pkg["json_url"],
            "timeline": pkg["timeline"],
            "appendices": pkg["appendices"],
        },
    }
