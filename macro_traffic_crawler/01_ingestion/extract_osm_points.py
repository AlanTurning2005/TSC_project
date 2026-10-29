"""
extract_osm_points.py
Trich xuat toa do cac doan duong chinh tu map.osm trong TSC_project
lam danh sach diem do (sampling points) cho TomTom Traffic Flow API.
"""

import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Đảm bảo import config từ thư mục gốc macro_traffic_crawler
_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from config import OSM_MAP_PATH, POINTS_FILE, DEFAULT_BBOX

PRIORITY_HIGHWAYS = {
    "trunk", "primary", "secondary", "tertiary",
    "trunk_link", "primary_link", "secondary_link", "tertiary_link"
}

# ==============================================================================
# QUY CHUẨN SỐ LÀN XE DỰ PHÒNG THEO TCVN 104:2007 (BẢNG 10 & BẢNG 7)
# Bảng 10 quy định "Chiều rộng một làn xe, và số làn xe tối thiểu" (tổng 2 chiều):
# - Đường cao tốc đô thị / trunk: tối thiểu 4 làn, mong muốn 6-10 làn -> 3 làn/hướng
# - Đường phố chính đô thị chủ yếu (primary): tối thiểu 6 làn -> 3 làn/hướng
# - Đường phố chính đô thị thứ yếu (secondary): tối thiểu 4 làn -> 2 làn/hướng
# - Đường phố gom (tertiary): tối thiểu 2 làn, mong muốn 4-6 làn -> 2 làn/hướng
# - Đường phố nội bộ (residential): tối thiểu 1 làn -> 1 làn/hướng
# - Nhánh rẽ nút giao (*_link): thiết kế 1 làn xe chạy chuyên dụng
# Ghi chú: Chỉ sử dụng bảng này khi OpenStreetMap không có sẵn tag 'lanes'.
# ==============================================================================
DEFAULT_LANES_BY_HIGHWAY = {
    "motorway": 3, "motorway_link": 1,
    "trunk": 3, "trunk_link": 1,
    "primary": 3, "primary_link": 1,
    "secondary": 2, "secondary_link": 1,
    "tertiary": 2, "tertiary_link": 1,
    "residential": 1, "unclassified": 1
}

def parse_osm_lanes(tags: dict) -> int:
    """
    Xác định số làn xe chạy một chiều (lanes per direction).
    1. Ưu tiên trích xuất từ tag 'lanes' của OpenStreetMap.
    2. Nếu thiếu tag, áp dụng Bảng 10 TCVN 104:2007 làm heuristic fallback.
    """
    highway = tags.get("highway", "primary")
    raw_lanes = tags.get("lanes")
    is_oneway = tags.get("oneway") in ["yes", "1", "true", "-1"]

    if raw_lanes:
        try:
            total = int(raw_lanes)
            # Nếu là đường 1 chiều: số làn = total.
            # Nếu là đường 2 chiều mà chỉ ghi tổng số làn: chia đôi lấy 1 hướng (tối thiểu 1 làn).
            return max(1, total if is_oneway else total // 2)
        except ValueError:
            pass

    return DEFAULT_LANES_BY_HIGHWAY.get(highway, 2)

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
                lanes = parse_osm_lanes(tags)
                ways.append({
                    "way_id": elem.attrib.get("id"),
                    "name": name,
                    "highway": highway,
                    "lanes": lanes,
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
            "lanes": way["lanes"],
            "lat": round(mid_lat, 6),
            "lon": round(mid_lon, 6)
        })

        if len(sampling_points) >= max_points:
            break

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["point_id", "road_name", "highway_type", "lanes", "lat", "lon"])
        writer.writeheader()
        writer.writerows(sampling_points)

    print(f"[OK] Da luu {len(sampling_points)} diem do (kem thong so lanes) vao: {output_file}")
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
                "lanes": 3,
                "lat": round(lat, 6),
                "lon": round(lon, 6)
            })
            idx += 1

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["point_id", "road_name", "highway_type", "lanes", "lat", "lon"])
        writer.writeheader()
        writer.writerows(points)

    print(f"[OK] Da tao {len(points)} diem luoi vao: {output_file}")
    return points

if __name__ == "__main__":
    extract_sampling_points(OSM_MAP_PATH, POINTS_FILE, max_points=100)
