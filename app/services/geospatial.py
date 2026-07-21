"""
Geospatial hotspot detection for GET /hotspots (GROUND_RULES 6.3):

    GET /hotspots?state=&district=&days=30
    -> {clusters[], heatmap_data[]}

Uses DBSCAN over case coordinates (haversine metric so eps is in real
km, not degrees) — this matches the "DBSCAN" tool named for the
Intelligence Engine in the project brief's tech stack section.
"""
import hashlib
import math
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.cluster import DBSCAN

from app.services.graph_store import GraphStore

EARTH_RADIUS_KM = 6371.0088


def _within_days(created_at: str | None, days: int) -> bool:
    if not created_at:
        return True
    try:
        ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return ts >= datetime.now(timezone.utc) - timedelta(days=days)


def find_hotspots(
    store: GraphStore,
    state: str | None = None,
    district: str | None = None,
    days: int = 30,
    eps_km: float = 5.0,
    min_samples: int = 2,
) -> dict:
    rows = store.all_case_locations()
    points = []
    meta = []
    for row in rows:
        loc = row["location"]
        if state and (loc.get("state") or "").lower() != state.lower():
            continue
        if district and (loc.get("district") or "").lower() != district.lower():
            continue
        if not _within_days(row["case"].get("created_at"), days):
            continue
        points.append([math.radians(loc["lat"]), math.radians(loc["lng"])])
        meta.append(row)

    heatmap_data = [
        {"lat": row["location"]["lat"], "lng": row["location"]["lng"], "weight": 1.0}
        for row in meta
    ]

    if len(points) < min_samples:
        return {"clusters": [], "heatmap_data": heatmap_data}

    X = np.array(points)
    db = DBSCAN(eps=eps_km / EARTH_RADIUS_KM, min_samples=min_samples, metric="haversine")
    labels = db.fit_predict(X)

    clusters = []
    for label in sorted(set(labels)):
        if label == -1:
            continue  # noise
        idxs = [i for i, l in enumerate(labels) if l == label]
        lats = [meta[i]["location"]["lat"] for i in idxs]
        lngs = [meta[i]["location"]["lng"] for i in idxs]
        center = {"lat": sum(lats) / len(lats), "lng": sum(lngs) / len(lngs)}
        radius_km = max(
            (_haversine_km(center["lat"], center["lng"], meta[i]["location"]["lat"], meta[i]["location"]["lng"]))
            for i in idxs
        )
        types = [meta[i]["case"].get("type") for i in idxs if meta[i]["case"].get("type")]
        dominant_type = max(set(types), key=types.count) if types else None
        digest = hashlib.sha1(f"{center['lat']:.4f},{center['lng']:.4f}".encode()).hexdigest()[:6]

        clusters.append({
            "cluster_id": f"hotspot_{digest}",
            "center": center,
            "radius_km": round(radius_km, 2),
            "case_count": len(idxs),
            "dominant_type": dominant_type,
            "district": meta[idxs[0]]["location"].get("district"),
            "state": meta[idxs[0]]["location"].get("state"),
        })

    clusters.sort(key=lambda c: c["case_count"], reverse=True)
    return {"clusters": clusters, "heatmap_data": heatmap_data}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
