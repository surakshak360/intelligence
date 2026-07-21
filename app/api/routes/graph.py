from fastapi import APIRouter, Depends

from app.api.deps import get_graph_store
from app.core.exceptions import NotFoundError
from app.core.schemas import GraphQueryRequest
from app.services.graph_store import GraphStore

router = APIRouter(tags=["graph"])


@router.post("/graph/query")
async def graph_query(
    payload: GraphQueryRequest,
    store: GraphStore = Depends(get_graph_store),
) -> dict:
    if not store.get_node(payload.entity_type, payload.entity_id):
        raise NotFoundError(
            f"No {payload.entity_type} node with id '{payload.entity_id}'.",
            {"entity_type": payload.entity_type, "entity_id": payload.entity_id},
        )

    sub = store.subgraph_bfs(payload.entity_type, payload.entity_id, payload.depth)

    nodes = [
        {"id": n, "label": d["label"], "properties": d["properties"]}
        for n, d in sub.nodes(data=True)
    ]
    edges = [
        {"source": u, "target": v, "type": d.get("type"), "properties": d.get("properties", {})}
        for u, v, d in sub.edges(data=True)
    ]

    # Connected components within the returned subgraph, excluding singletons.
    undirected = sub.to_undirected()
    clusters = []
    for i, component in enumerate(_connected_components(undirected)):
        if len(component) > 1:
            clusters.append({"cluster_id": f"local_cluster_{i}", "node_ids": sorted(component), "size": len(component)})

    return {"job_id": None, "status": "completed", "result": {"nodes": nodes, "edges": edges, "clusters": clusters}}


def _connected_components(graph):
    import networkx as nx
    return list(nx.connected_components(graph))
