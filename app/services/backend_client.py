"""
Backend Client for Intelligence Engine — retrieves historical cases & evidence from Backend API Gateway (Port 8000)
and populates them into the in-memory GraphStore for multi-case intelligence fusion, linkage, and network analysis.
"""
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.core.config import get_settings
from app.services.graph_store import GraphStore

logger = logging.getLogger(__name__)


class BackendClient:
    def __init__(self, base_url: Optional[str] = None):
        settings = get_settings()
        self.base_url = (base_url or settings.BACKEND_URL).rstrip("/")
        # Service token header to bypass citizen filtering and receive all cases
        self.headers = {"Authorization": "Bearer service_token"}

    async def fetch_all_cases(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch cases list from Backend Gateway API."""
        url = f"{self.base_url}/api/v1/cases?page_size={limit}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        inner = data["data"]
                        if isinstance(inner, dict) and "items" in inner:
                            return inner["items"]
                        elif isinstance(inner, list):
                            return inner
                    elif isinstance(data, list):
                        return data
                logger.warning(f"Backend GET /api/v1/cases returned status {resp.status_code}")
            except Exception as e:
                logger.warning(f"Failed to fetch cases from backend API ({self.base_url}): {e}")
        return []

    async def fetch_case_evidence(self, case_id: str) -> List[Dict[str, Any]]:
        """Fetch evidence for a specific case from Backend Gateway API."""
        url = f"{self.base_url}/api/v1/cases/{case_id}/evidence"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        return data["data"] if isinstance(data["data"], list) else []
                    elif isinstance(data, list):
                        return data
            except Exception as e:
                logger.warning(f"Failed to fetch evidence for case {case_id}: {e}")
        return []

    async def sync_cases_to_graph(self, store: GraphStore) -> int:
        """
        Fetch cases + evidence from backend gateway and ingest into GraphStore.
        Returns the number of cases successfully synced.
        """
        cases = await self.fetch_all_cases()
        synced_count = 0
        for case_item in cases:
            case_id = str(case_item.get("id"))
            if not case_id:
                continue

            ev_list = await self.fetch_case_evidence(case_id)

            combined_scam: Dict[str, Any] = {}
            combined_vision: Dict[str, Any] = {}
            for ev in ev_list:
                ml_res = ev.get("ml_results") or {}
                if isinstance(ml_res, dict):
                    if "scam_intelligence" in ml_res and isinstance(ml_res["scam_intelligence"], dict):
                        combined_scam.update(ml_res["scam_intelligence"])
                    if "vision_intelligence" in ml_res and isinstance(ml_res["vision_intelligence"], dict):
                        combined_vision.update(ml_res["vision_intelligence"])
                if ev.get("text_content") and not combined_scam:
                    combined_scam = {"original_text": ev.get("text_content")}

            user_report = {
                "reporter_id": case_item.get("reporter_id"),
                "case_type": case_item.get("type"),
                "priority": case_item.get("priority"),
                "location": case_item.get("location"),
                "summary": case_item.get("summary"),
            }

            store.ingest_case(case_id, combined_scam, combined_vision, user_report)
            synced_count += 1

        return synced_count


backend_client = BackendClient()
