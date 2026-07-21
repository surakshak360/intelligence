"""
Case linking: find other cases that share indicator entities (phone
numbers, accounts, devices, IPs, locations, scam templates) with the
case currently being fused.

This directly implements the `linked_cases` field of the /fuse contract
(GROUND_RULES 6.3):

    "linked_cases": [
      {"case_id": "case_xyz", "similarity": 0.87,
       "shared_entities": ["+919876543210", "HDFC_0045"]}
    ]
"""
from app.services.graph_store import GraphStore


def find_linked_cases(store: GraphStore, case_id: str, top_n: int = 10) -> list[dict]:
    own_entities = store.case_linked_entity_keys(case_id)
    if not own_entities:
        return []

    # case_id -> set of shared node keys
    shared: dict[str, set[str]] = {}
    for node_key in own_entities:
        for other_case in store.cases_linked_to(node_key, exclude_case=case_id):
            shared.setdefault(other_case, set()).add(node_key)

    results = []
    for other_case_id, shared_nodes in shared.items():
        other_entities = store.case_linked_entity_keys(other_case_id)
        union = own_entities | other_entities
        similarity = round(len(shared_nodes) / len(union), 4) if union else 0.0
        shared_values = []
        for node_key in shared_nodes:
            label, _, entity_id = node_key.partition(":")
            shared_values.append(entity_id)
        results.append({
            "case_id": other_case_id,
            "similarity": similarity,
            "shared_entities": sorted(shared_values),
        })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:top_n]
