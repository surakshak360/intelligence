# surakshak360-intelligence

The Intelligence Fusion service. Owns: graph analytics (fraud network
linking), risk fusion, geospatial hotspot detection, evidence package
generation, and rule-based recommendations.

**No model training. CPU only.** (GROUND_RULES.md §10.1)

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Railway liveness/readiness probe |
| GET | `/schema` | Machine-readable endpoint schema |
| POST | `/fuse` | Fuse scam + vision + citizen-report signals into a risk score, linked cases, network analysis, evidence package, and recommendations |
| POST | `/graph/query` | BFS the fraud graph from an entity |
| POST | `/evidence/generate` | Generate a fresh PDF/JSON evidence package for an already-fused case |
| GET | `/hotspots` | DBSCAN-clustered fraud hotspots |
| GET | `/jobs/{job_id}` | Poll a completed job (compatibility with the generic async ML client pattern in GROUND_RULES §4.2) |

All response shapes match `GROUND_RULES.md` §6.3 exactly.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Try it:

```bash
curl localhost:8000/health

curl -X POST localhost:8000/fuse -H "Content-Type: application/json" -d '{
  "case_id": "case_1",
  "scam_result": {
    "risk_score": 0.94, "scam_type": "digital_arrest", "confidence": 0.91,
    "transcript": "This is CBI, you are under digital arrest.",
    "entities": [{"type": "phone", "value": "+919876543210"}]
  },
  "user_report": {
    "reporter_id": "u1", "priority": "high", "case_type": "digital_arrest",
    "location": {"lat": 28.6139, "lng": 77.2090, "district": "New Delhi", "state": "Delhi"}
  }
}'
```

## Testing before you push

```bash
pytest -xvs                                   # full run, verbose
pytest --cov=app --cov-report=term-missing    # coverage (target: 80%, per GROUND_RULES §14)
```

The suite spins the whole FastAPI app up in-process (`TestClient`) — no
Docker, no Mongo, no Neo4j required. It covers: `/health` + `/schema`
contract shape, `/fuse` end-to-end including two cases getting linked
because they share a phone-number entity, validation errors, `/graph/query`
BFS + 404 handling, `/evidence/generate` (including the "must fuse first"
404), and `/hotspots` DBSCAN clustering (including the empty-graph case).

State (the graph, case registry, job store) is process-local and reset
between tests via the `_reset_state` autouse fixture in `tests/conftest.py`.

## Architecture: NetworkX now, Neo4j-ready

`app/services/graph_store.py` implements the Neo4j schema from
GROUND_RULES §5.2 on top of NetworkX, entirely in memory. Every other
module in this service talks only to `GraphStore`'s public methods —
never to NetworkX directly — so swapping to a real Neo4j-backed
implementation later is contained to that one file. Set `NEO4J_URI` /
`NEO4J_USER` / `NEO4J_PASSWORD` when that swap happens; `/health` already
reports which backend is active.

One schema extension beyond §5.2: a `(:Case)-[:INVOLVES]->(:Entity)`
relationship, used to link a case straight to its raw indicator entities
(phone/account/device/IP) before an identified `:Person` exists — which
is the normal state of a freshly reported case.

## Folder structure

```
app/
├── main.py                   # FastAPI app factory, middleware, static evidence serving
├── core/
│   ├── config.py              # env-driven Settings
│   ├── logging.py             # structured JSON logs + request-id context
│   ├── exceptions.py          # ServiceError -> GROUND_RULES §2.3 error envelope
│   └── schemas.py             # all request/response Pydantic models
├── api/
│   ├── deps.py                 # FastAPI dependency providers
│   ├── router.py                # aggregates all route modules
│   └── routes/
│       ├── health.py           # GET /health, GET /schema
│       ├── fuse.py             # POST /fuse
│       ├── graph.py            # POST /graph/query
│       ├── evidence.py         # POST /evidence/generate
│       ├── hotspots.py         # GET /hotspots
│       └── jobs.py             # GET /jobs/{job_id}
├── services/
│   ├── graph_store.py          # NetworkX graph engine (Neo4j schema)
│   ├── fusion.py               # deterministic weighted risk fusion (§10.2)
│   ├── linking.py              # shared-entity case linking
│   ├── network_analysis.py     # cluster detection, central entities, pattern label
│   ├── geospatial.py           # DBSCAN hotspot clustering
│   ├── evidence.py             # PDF (ReportLab) + JSON evidence packages (§10.3)
│   └── recommendations.py      # citizen/officer/analyst rule engine
├── models/
│   ├── job_store.py             # in-memory job registry
│   └── case_registry.py         # in-memory case_id -> last fuse result
└── data/                        # (reserved — no seed data ships by default)
tests/
├── conftest.py
├── test_health.py
├── test_fuse.py
├── test_graph_and_evidence.py
├── test_hotspots.py
└── test_jobs.py
Dockerfile
railway.toml
requirements.txt
.env.example
pytest.ini
.github/workflows/ci.yml
```

