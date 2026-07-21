from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_graph_store
from app.services import geospatial
from app.services.graph_store import GraphStore

router = APIRouter(tags=["hotspots"])


@router.get("/hotspots")
async def hotspots(
    state: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    store: GraphStore = Depends(get_graph_store),
) -> dict:
    result = geospatial.find_hotspots(store, state=state, district=district, days=days)
    return {"job_id": None, "status": "completed", "result": result}
