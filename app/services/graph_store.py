"""
GraphStore — the intelligence service's fraud-network graph engine.

GROUND_RULES.md section 5.2 defines the canonical schema this service
owns (node labels, relationship types). Section 9.4 puts intelligence on
CPU-only, and section 10.1 says "No Model Training — Graph algorithms
(NetworkX, Neo4j Cypher)".

This module implements that schema on top of NetworkX so the service has
*zero* external dependencies out of the box (works in CI, works on a
laptop, works on Railway's cheapest tier). If NEO4J_URI is configured
(section 5.2 marks Neo4j "optional"), swap this module's storage for a
Neo4j-backed adapter behind the same public methods — every call site in
routes/services only talks to GraphStore, never to NetworkX directly, so
that swap is contained to this one file.

Schema extension note: the base schema in GROUND_RULES only wires
indicator entities (PhoneNumber, Account, Device, IPAddress) to an
identified (:Person). In real intake, a case usually starts with raw
indicators and no identified person yet. We add one pragmatic
relationship type not in the original list — (:Case)-[:INVOLVES]->(:X)
— to link a case straight to its raw indicator entities before/without
attribution. Everything else follows the schema exactly.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Optional

import networkx as nx

NODE_LABELS = {
    "Person", "Account", "Device", "PhoneNumber", "IPAddress",
    "Transaction", "Case", "Location", "ScamTemplate",
}

# Base schema relationships (GROUND_RULES 5.2) + our documented INVOLVES extension.
REL_TYPES = {
    "OWNS", "USES", "CALLS", "CONNECTS_FROM", "REPORTED", "TRANSFERRED",
    "LINKED_TO", "OCCURRED_AT", "MATCHES", "INVOLVES",
}

# scam-intelligence / vision entity "type" -> graph node label
ENTITY_TYPE_TO_LABEL = {
    "phone": "PhoneNumber",
    "phone_number": "PhoneNumber",
    "account": "Account",
    "upi": "Account",
    "bank_account": "Account",
    "ip": "IPAddress",
    "ip_address": "IPAddress",
    "device": "Device",
    "imei": "Device",
}


def _node_key(label: str, entity_id: str) -> str:
    return f"{label}:{entity_id}"


class GraphStore:
    """Thread-safe, in-process graph over the whole service lifetime."""

    def __init__(self) -> None:
        self._g = nx.MultiDiGraph()
        self._lock = threading.RLock()

    # -- low level -----------------------------------------------------

    def upsert_node(self, label: str, entity_id: str, properties: Optional[dict] = None) -> str:
        assert label in NODE_LABELS, f"Unknown node label: {label}"
        key = _node_key(label, entity_id)
        with self._lock:
            if self._g.has_node(key):
                self._g.nodes[key]["properties"].update(properties or {})
            else:
                self._g.add_node(key, label=label, entity_id=entity_id, properties=properties or {})
        return key

    def add_edge(
        self, src_label: str, src_id: str, rel_type: str,
        dst_label: str, dst_id: str, properties: Optional[dict] = None,
    ) -> None:
        assert rel_type in REL_TYPES, f"Unknown relationship type: {rel_type}"
        src_key = self.upsert_node(src_label, src_id)
        dst_key = self.upsert_node(dst_label, dst_id)
        with self._lock:
            # Avoid duplicate parallel edges of the same type between the same pair.
            for _, _, data in self._g.out_edges(src_key, data=True):
                pass
            existing = self._g.get_edge_data(src_key, dst_key) or {}
            for _, edata in existing.items():
                if edata.get("type") == rel_type:
                    edata["properties"].update(properties or {})
                    return
            self._g.add_edge(src_key, dst_key, type=rel_type, properties=properties or {})

    # -- ingestion -------------------------------------------------------

    def ingest_case(
        self,
        case_id: str,
        scam_result: Optional[dict] = None,
        vision_result: Optional[dict] = None,
        user_report: Optional[dict] = None,
    ) -> list[str]:
        """
        Materialize a case + everything we can extract from the upstream
        AI outputs into the graph. Returns the list of node keys the case
        is now linked to (used by linking.py for shared-entity lookup).
        """
        user_report = user_report or {}
        now = datetime.now(timezone.utc).isoformat()

        case_props = {
            "type": user_report.get("case_type") or (scam_result or {}).get("scam_type") or "other",
            "status": "new",
            "risk_score": None,  # filled in by fusion after this call
            "created_at": now,
        }
        self.upsert_node("Case", case_id, case_props)
        linked_keys: list[str] = []

        # Reporter
        reporter_id = user_report.get("reporter_id")
        if reporter_id:
            self.upsert_node("Person", reporter_id, {})
            self.add_edge("Person", reporter_id, "REPORTED", "Case", case_id)

        # Location
        location = user_report.get("location")
        if location and "lat" in location and "lng" in location:
            loc_id = f"{location['lat']:.4f},{location['lng']:.4f}"
            self.upsert_node("Location", loc_id, {
                "lat": location["lat"],
                "lng": location["lng"],
                "district": location.get("district"),
                "state": location.get("state"),
                "pincode": location.get("pincode"),
            })
            self.add_edge("Case", case_id, "OCCURRED_AT", "Location", loc_id)
            linked_keys.append(_node_key("Location", loc_id))

        # Scam template match
        scam_type = (scam_result or {}).get("scam_type")
        if scam_type:
            self.upsert_node("ScamTemplate", scam_type, {"name": scam_type})
            self.add_edge(
                "Case", case_id, "MATCHES", "ScamTemplate", scam_type,
                {"confidence": (scam_result or {}).get("confidence", 0.0)},
            )

        # Indicator entities from scam-intelligence output.
        # Format 1: entities: [{"type": "phone", "value": "...", ...}]  (original spec)
        # Format 2: identifiers: {"phone_numbers": [...], "upi_ids": [...], ...}  (actual output)
        for ent in (scam_result or {}).get("entities", []):
            label = ENTITY_TYPE_TO_LABEL.get(str(ent.get("type", "")).lower())
            value = ent.get("value") or ent.get("text")
            if not label or not value:
                continue
            self.upsert_node(label, str(value), {k: v for k, v in ent.items() if k not in ("value", "text")})
            self.add_edge("Case", case_id, "INVOLVES", label, str(value))
            linked_keys.append(_node_key(label, str(value)))

        # Format 2: identifiers dict from scam-intelligence actual output
        identifiers = (scam_result or {}).get("identifiers", {})
        for phone in identifiers.get("phone_numbers", []):
            self.upsert_node("PhoneNumber", phone, {"source": "scam_intelligence"})
            self.add_edge("Case", case_id, "INVOLVES", "PhoneNumber", phone)
            linked_keys.append(_node_key("PhoneNumber", phone))
        for upi in identifiers.get("upi_ids", []):
            self.upsert_node("Account", upi, {"type": "upi", "source": "scam_intelligence"})
            self.add_edge("Case", case_id, "INVOLVES", "Account", upi)
            linked_keys.append(_node_key("Account", upi))
        for url in identifiers.get("urls", []):
            self.upsert_node("Device", url, {"type": "url", "source": "scam_intelligence"})
            self.add_edge("Case", case_id, "INVOLVES", "Device", url)
            linked_keys.append(_node_key("Device", url))

        # Vision indicator: detected counterfeit class becomes a ScamTemplate too
        detected_class = (vision_result or {}).get("detected_class")
        if detected_class:
            self.upsert_node("ScamTemplate", detected_class, {"name": detected_class, "modality": "vision"})
            self.add_edge(
                "Case", case_id, "MATCHES", "ScamTemplate", detected_class,
                {"confidence": (vision_result or {}).get("confidence", 0.0)},
            )
            linked_keys.append(_node_key("ScamTemplate", detected_class))

        return linked_keys

    def set_case_risk(self, case_id: str, risk_score: float, risk_level: str) -> None:
        key = _node_key("Case", case_id)
        with self._lock:
            if self._g.has_node(key):
                self._g.nodes[key]["properties"]["risk_score"] = risk_score
                self._g.nodes[key]["properties"]["risk_level"] = risk_level

    # -- reads -----------------------------------------------------------

    def has_case(self, case_id: str) -> bool:
        return self._g.has_node(_node_key("Case", case_id))

    def get_node(self, label: str, entity_id: str) -> Optional[dict]:
        key = _node_key(label, entity_id)
        if not self._g.has_node(key):
            return None
        data = self._g.nodes[key]
        return {"id": key, "label": data["label"], "properties": data["properties"]}

    def case_count(self) -> int:
        with self._lock:
            return sum(1 for _, d in self._g.nodes(data=True) if d.get("label") == "Case")

    def cases_linked_to(self, node_key: str, exclude_case: str) -> set[str]:
        """All Case entity_ids (other than exclude_case) connected to node_key
        via any edge direction (covers Case-INVOLVES->X and Case-OCCURRED_AT->X)."""
        result: set[str] = set()
        if not self._g.has_node(node_key):
            return result
        for nbr in set(self._g.predecessors(node_key)) | set(self._g.successors(node_key)):
            data = self._g.nodes[nbr]
            if data.get("label") == "Case" and data.get("entity_id") != exclude_case:
                result.add(data["entity_id"])
        return result

    def case_linked_entity_keys(self, case_id: str) -> set[str]:
        key = _node_key("Case", case_id)
        if not self._g.has_node(key):
            return set()
        return set(self._g.successors(key)) | set(self._g.predecessors(key))

    def subgraph_bfs(self, start_label: str, start_id: str, depth: int) -> nx.MultiDiGraph:
        start_key = _node_key(start_label, start_id)
        if not self._g.has_node(start_key):
            return nx.MultiDiGraph()
        undirected = self._g.to_undirected(as_view=True)
        visited = {start_key}
        frontier = {start_key}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                next_frontier |= set(undirected.neighbors(node))
            next_frontier -= visited
            visited |= next_frontier
            frontier = next_frontier
            if not frontier:
                break
        return self._g.subgraph(visited).copy()

    def all_case_locations(self) -> list[dict]:
        """(case_id, case_props, location_props) for every case with a Location."""
        out = []
        with self._lock:
            for node, data in self._g.nodes(data=True):
                if data.get("label") != "Case":
                    continue
                case_id = data["entity_id"]
                for nbr in self._g.successors(node):
                    ed = self._g.get_edge_data(node, nbr)
                    if any(e.get("type") == "OCCURRED_AT" for e in ed.values()):
                        loc = self._g.nodes[nbr]["properties"]
                        out.append({"case_id": case_id, "case": data["properties"], "location": loc})
        return out

    def snapshot(self) -> nx.MultiDiGraph:
        with self._lock:
            return self._g.copy()


graph_store = GraphStore()
