# Integrating surakshak360-intelligence with the rest of Surakshak360

This service is consumed by **one caller only**: `surakshak360-backend`.
The frontend, scam-intelligence, and vision services never talk to this
service directly — everything routes through the backend, per
GROUND_RULES.md §1 (API-First) and §4.1 (Service Discovery).

```
citizen / officer
      │
      ▼
surakshak360-frontend  (Vercel)
      │  REST, wrapped in success/data envelope (§2.2)
      ▼
surakshak360-backend   (Railway)
      │  raw job/result shape (§6), private networking
      ├──▶ surakshak360-scam-intelligence
      ├──▶ surakshak360-vision
      └──▶ surakshak360-intelligence   ◀── THIS REPO
                 │
                 ▼
        MongoDB (via backend) + local evidence storage (Cloudinary in prod)
```

## 1. Service discovery (backend side)

Per GROUND_RULES §4.1, the backend reaches this service over Railway's
private network:

```
INTELLIGENCE_URL=http://intelligence:8000     # production (Railway internal DNS)
INTELLIGENCE_URL=http://localhost:8001         # local dev, if you run this on 8001
                                                # to avoid clashing with backend on 8000
```

Add that to `surakshak360-backend/.env` — it's already listed in
GROUND_RULES §12.1's backend env var block.

## 2. When the backend should call this service

The natural trigger point is: **after both `scam-intelligence` and/or
`vision` have returned a result for a case's evidence**, the backend
calls `POST /fuse` here to get the fused risk score, linked cases, and
evidence package — then persists `intelligence_output` on the `evidence`
document (see the Mongo schema in GROUND_RULES §5.1).

```python
# surakshak360-backend/app/services/ml_client.py  (illustrative)
import httpx
from app.core.config import settings

async def call_intelligence_fuse(case_id: str, scam_result: dict | None,
                                  vision_result: dict | None, user_report: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:  # 10s per §4.4
        resp = await client.post(
            f"{settings.INTELLIGENCE_URL}/fuse",
            json={
                "case_id": case_id,
                "scam_result": scam_result,
                "vision_result": vision_result,
                "user_report": user_report,
            },
        )
        resp.raise_for_status()
        return resp.json()["result"]
```

Apply the retry/backoff policy from §4.4 (`intelligence`: 10s timeout, 3
retries, 1s/2s/3s backoff) around this call — this service does not
retry for you, the caller owns that per the contract.

## 3. Exact request/response contract

This service does **not** use the `{"success": true, "data": ...}`
envelope from GROUND_RULES §2.2 — that envelope is the
frontend-facing backend API shape. Internal ML services (scam-intelligence,
vision, intelligence) use the flatter shape from §6:

```json
// Request: POST /fuse
{
  "case_id": "case_abc",
  "scam_result": { ... output from scam-intelligence ... },   // optional
  "vision_result": { ... output from vision ... },             // optional
  "user_report": {
    "reporter_id": "user_123",
    "priority": "high",
    "case_type": "digital_arrest",
    "location": {"lat": 28.6139, "lng": 77.2090, "district": "New Delhi", "state": "Delhi"}
  }
}
```

```json
// Response: 200 OK
{
  "job_id": "job_abc123",
  "status": "completed",
  "result": {
    "case_id": "case_abc",
    "risk_level": "critical",
    "overall_score": 0.93,
    "linked_cases": [{"case_id": "...", "similarity": 0.87, "shared_entities": ["..."]}],
    "network_analysis": {"cluster_id": "...", "size": 23, "central_entities": [...], "pattern": "mule_network", "jurisdictions": [...]},
    "evidence_package": {"pdf_url": "...", "json_url": "...", "includes": [...]},
    "recommendations": {"citizen": [...], "officer": [...], "analyst": [...]},
    "processing_time_ms": 42
  }
}
```

```json
// Error response (any 4xx/5xx) — matches GROUND_RULES §2.3 error codes
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request failed validation.",
    "details": {"errors": [...]},
    "request_id": "req_xxxxx"
  }
}
```

The backend should map this service's `NOT_FOUND` / `VALIDATION_ERROR`
straight through to the frontend inside its own §2.2 envelope — no
translation needed, the codes already match §2.3.

## 4. Backend responsibilities before calling this service

Per §4.3 ("Input Validation (Backend Responsibility)"), **this service
assumes valid input** and does not re-validate upstream ML output — the
backend must:
- confirm `case_id` is a real case in Mongo before calling `/fuse`
- pass through `scam_result` / `vision_result` exactly as returned by
  those services, unmodified
- supply `user_report.location` as `{lat, lng}` (not GeoJSON
  `[lng, lat]` — this service uses plain `{lat, lng}` keys, the backend
  will need to convert from Mongo's GeoJSON `Point` format)

## 5. Running the whole pipeline locally (all repos together)

There's no `docker-compose.yml` in *this* repo (it's owned centrally, per
`surakshak360-docs`), but here's the minimum to test backend ↔
intelligence integration on one machine:

```bash
# Terminal 1 — this service
cd surakshak360-intelligence
uvicorn app.main:app --reload --port 8001

# Terminal 2 — backend, pointed at it
cd surakshak360-backend
INTELLIGENCE_URL=http://localhost:8001 uvicorn app.main:app --reload --port 8000
```

Then hit the backend's case endpoint and confirm it successfully proxies
to `http://localhost:8001/fuse` and gets a `200`.

## 6. Contract testing

Per GROUND_RULES §14 ("Contract: Pact / Schemathesis, All endpoints"),
this service's `GET /schema` is the source of truth for its own I/O
shapes. A lightweight contract check (already wired into
`.github/workflows/ci.yml` here) just asserts `/health` and `/schema`
come up clean on every push — the backend team can add a Schemathesis
run against `INTELLIGENCE_URL/schema` in their own CI once staging URLs
exist.

## 7. What changes when this moves off the hackathon defaults

| Default now | Production swap | File to change |
|---|---|---|
| In-memory NetworkX graph | Neo4j | `app/services/graph_store.py` — set `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` |
| Local disk evidence storage | Cloudinary/S3 | `app/services/evidence.py` — `_save_file()` |
| In-memory job store | Redis-backed queue | `app/models/job_store.py` |
| In-memory case registry | Read from Mongo `evidence` collection | `app/models/case_registry.py` |

None of these swaps require touching `app/api/routes/*.py` or any of the
business logic in `fusion.py` / `linking.py` / `network_analysis.py` —
they only talk to the interfaces above, not the storage directly.
