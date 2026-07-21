from fastapi import APIRouter, Depends

from app.api.deps import get_job_store
from app.core.exceptions import NotFoundError
from app.models.job_store import JobStore

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, jobs: JobStore = Depends(get_job_store)) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise NotFoundError(f"No job '{job_id}'.", {"job_id": job_id})
    return job
