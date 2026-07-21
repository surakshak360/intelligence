"""
Tiny in-memory registry mapping case_id -> last fusion result + raw
inputs. Lets POST /evidence/generate be called on its own (per the
GROUND_RULES contract, it takes only {case_id, format} — no fusion
payload) by reusing whatever /fuse already computed for that case.

Same caveat as job_store.py: process-local and non-persistent. In
production this is just a read against MongoDB's `evidence` collection
(section 5.1), which the backend already owns — this stub exists so the
service is independently runnable/testable without a backend attached.
"""
import threading
from typing import Any, Optional


class CaseRegistry:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def save(self, case_id: str, fuse_result: dict, raw_inputs: dict) -> None:
        with self._lock:
            self._store[case_id] = {"fuse_result": fuse_result, "raw_inputs": raw_inputs}

    def get(self, case_id: str) -> Optional[dict]:
        with self._lock:
            return self._store.get(case_id)


case_registry = CaseRegistry()
