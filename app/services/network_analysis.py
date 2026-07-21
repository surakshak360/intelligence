"""
Network analysis over the subgraph around a case: cluster detection,
central entities, a heuristic pattern label, and jurisdictions — the
`network_analysis` block of the /fuse contract (GROUND_RULES 6.3):

    "network_analysis": {
      "cluster_id": "cluster_mumbai_042",
      "size": 23,
      "central_entities": ["+919876543210", "IMEI_8675309"],
      "pattern": "mule_network",
      "jurisdictions": ["Mumbai", "Thane", "Navi Mumbai"]
    }
"""
import hashlib

import networkx as nx

from app.services.graph_store import GraphStore

PATTERN_LABEL_LOOKUP = {
    frozenset({"Account"}): "mule_network",
    frozenset({"Account", "PhoneNumber"}): "mule_network",
    frozenset({"PhoneNumber"}): "call_campaign",
    frozenset({"PhoneNumber", "IPAddress"}): "phishing_ring",
    frozenset({"ScamTemplate"}): "templated_scam_campaign",
    frozenset({"Device"}): "device_farm",
}


def _cluster_id(seed_case_id: str, node_keys: set[str]) -> str:
    digest = hashlib.sha1("|".join(sorted(node_keys)).encode()).hexdigest()[:6]
    return f"cluster_{digest}"


def analyze_network(store: GraphStore, case_id: str, linked_case_ids: list[str]) -> dict:
    sub = store.subgraph_bfs("Case", case_id, depth=2)

    if sub.number_of_nodes() <= 1:
        return {
            "cluster_id": None,
            "size": 1,
            "central_entities": [],
            "pattern": "isolated_report",
            "jurisdictions": [],
        }

    undirected = sub.to_undirected()
    centrality = nx.degree_centrality(undirected)
    ranked = sorted(centrality.items(), key=lambda kv: kv[1], reverse=True)

    central_entities = []
    labels_present: set[str] = set()
    jurisdictions: set[str] = set()

    for node_key, _score in ranked:
        data = sub.nodes[node_key]
        label = data.get("label")
        labels_present.add(label)
        if label == "Location":
            district = data["properties"].get("district")
            if district:
                jurisdictions.add(district)
        elif label != "Case" and len(central_entities) < 5:
            central_entities.append(data.get("entity_id"))

    pattern = PATTERN_LABEL_LOOKUP.get(frozenset(labels_present - {"Case", "Location"}), "emerging_pattern")

    case_nodes = {n for n, d in sub.nodes(data=True) if d.get("label") == "Case"}
    node_keys_for_id = {n for n in sub.nodes if sub.nodes[n].get("label") != "Case"}

    return {
        "cluster_id": _cluster_id(case_id, node_keys_for_id) if len(case_nodes) > 1 else None,
        "size": len(linked_case_ids) + 1,
        "central_entities": central_entities,
        "pattern": pattern,
        "jurisdictions": sorted(jurisdictions),
    }
