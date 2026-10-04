"""
extract_osm_points.py
Trich xuat toa do cac doan duong chinh tu map.osm trong TSC_project
lam danh sach diem do (sampling points) cho TomTom Traffic Flow API.
"""

import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from config import OSM_MAP_PATH, POINTS_FILE, DEFAULT_BBOX

PRIORITY_HIGHWAYS = {
    "trunk", "primary", "secondary", "tertiary",
    "trunk_link", "primary_link", "secondary_link", "tertiary_link"
}

def extract_sampling_points(osm_path: Path, output_file: Path, max_points: int = 50):
    print(f"[*] Dang doc file OSM: {osm_path}")
    if not osm_path.exists():
        print(f"[!] Khong tim thay file {osm_path}. Sinh cac diem luoi fallback.")
        return generate_fallback_grid(output_file)

    nodes = {}
    ways = []

    context = ET.iterparse(osm_path, events=("end",))
    for event, elem in context:
        if elem.tag == "node":
            node_id = elem.attrib.get("id")
            lat = float(elem.attrib.get("lat"))
            lon = float(elem.attrib.get("lon"))
            nodes[node_id] = (lat, lon)
            elem.clear()
        elif elem.tag == "way":
            tags = {child.attrib.get("k"): child.attrib.get("v") for child in elem if child.tag == "tag"}
            highway = tags.get("highway")
            name = tags.get("name") or tags.get("name:en") or tags.get("name:vi") or "Unnamed Road"

            if highway in PRIORITY_HIGHWAYS:
                nd_refs = [child.attrib.get("ref") for child in elem if child.tag == "nd"]
                ways.append({
                    "way_id": elem.attrib.get("id"),
                    "name": name,
                    "highway": highway,
                    "nodes": nd_refs
                })
            elem.clear()

    print(f"[*] Tim thay {len(nodes)} nodes va {len(ways)} doan duong uu tien.")

    sampling_points = []
    seen_coords = set()

    for way in ways:
        valid_coords = [nodes[ref] for ref in way["nodes"] if ref in nodes]
        if not valid_coords:
            continue

        mid_idx = len(valid_coords) // 2
        mid_lat, mid_lon = valid_coords[mid_idx]

        point_key = (round(mid_lat, 4), round(mid_lon, 4))
        if point_key in seen_coords:
            continue
        seen_coords.add(point_key)

        sampling_points.append({
            "point_id": f"way_{way['way_id']}",
            "road_name": way["name"],
            "highway_type": way["highway"],
            "lat": round(mid_lat, 6),
            "lon": round(mid_lon, 6)
        })

        if len(sampling_points) >= max_points:
            break

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["point_id", "road_name", "highway_type", "lat", "lon"])
        writer.writeheader()
        writer.writerows(sampling_points)

    print(f"[OK] Da luu {len(sampling_points)} diem do vao: {output_file}")
    return sampling_points

def generate_fallback_grid(output_file: Path, rows: int = 5, cols: int = 5):
    bbox = DEFAULT_BBOX
    lats = [bbox["min_lat"] + i * (bbox["max_lat"] - bbox["min_lat"]) / (rows - 1) for i in range(rows)]
    lons = [bbox["min_lon"] + j * (bbox["max_lon"] - bbox["min_lon"]) / (cols - 1) for j in range(cols)]

    points = []
    idx = 1
    for lat in lats:
        for lon in lons:
            points.append({
                "point_id": f"grid_{idx}",
                "road_name": f"Intersection Point {idx}",
                "highway_type": "primary",
                "lat": round(lat, 6),
                "lon": round(lon, 6)
            })
            idx += 1

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["point_id", "road_name", "highway_type", "lat", "lon"])
        writer.writeheader()
        writer.writerows(points)

    print(f"[OK] Da tao {len(points)} diem luoi vao: {output_file}")
    return points

if __name__ == "__main__":
    extract_sampling_points(OSM_MAP_PATH, POINTS_FILE, max_points=40)
