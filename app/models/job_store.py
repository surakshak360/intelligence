"""
Minimal in-memory job registry.

GROUND_RULES section 4.2 defines the *generic* ML service interface as
async (POST returns job_id + "processing", GET /jobs/{id} polls for the
result). The intelligence service's actual work (graph traversal,
rule-based fusion, DBSCAN clustering) is CPU-bound and fast — well inside
the 10s timeout in section 4.4 — so every POST endpoint here completes
synchronously and returns status="completed" in the same response
(matching the literal output example in section 6.3).

We still register each completed operation in this store so a
GET /jobs/{job_id} call from the backend (if it chooses to poll instead
of trusting the sync response) resolves correctly instead of 404ing.
This is intentionally process-local, in-memory, non-persistent — fine
for a stateless hackathon service; a real deployment would back this
with Redis (see GROUND_RULES 12.1 REDIS_URL) if async queuing is added.
"""
import threading
import uuid
from typing import Any, Optional


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def new_id(self) -> str:
        return f"job_{uuid.uuid4().hex[:12]}"

    def put_completed(self, job_id: str, endpoint: str, result: dict) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "endpoint": endpoint,
                "status": "completed",
                "result": result,
                "error": None,
            }

    def put_failed(self, job_id: str, endpoint: str, error: dict) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "endpoint": endpoint,
                "status": "failed",
                "result": None,
                "error": error,
            }

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            return self._jobs.get(job_id)


job_store = JobStore()
