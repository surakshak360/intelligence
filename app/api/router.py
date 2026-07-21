from fastapi import APIRouter

from app.api.routes import evidence, fuse, graph, health, hotspots, jobs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(fuse.router)
api_router.include_router(graph.router)
api_router.include_router(evidence.router)
api_router.include_router(hotspots.router)
api_router.include_router(jobs.router)
