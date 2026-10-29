"""
generate_sumo_counts.py
Bước 1 trong Pipeline Demand Modeling & Calibration:
Chuyển đổi dữ liệu chuỗi thời gian TomTom (CSV) thành file đếm mục tiêu chuẩn SUMO (edge_counts.xml)
phục vụ trực tiếp cho công cụ routeSampler.py.

Các tính năng cốt lõi:
1. Quy đổi PCU tham chiếu Tiêu chuẩn Việt Nam (TCVN 104:2007 Bảng 2, TCVN 4054:2005 Bảng 3).
2. Bảng phân tầng tỷ lệ phương tiện (Modal Split) theo cấp đường (highway_type) đặc thù TP.HCM.
3. Ánh xạ không gian (Spatial Matching): Chiếu tọa độ GPS (lat, lon) của TomTom lên mạng lưới SUMO
   để tìm chính xác đoạn cạnh (edge) gần nhất (giải quyết triệt để lỗi gán bừa vào đoạn #0).
4. Tự động tính thời lượng thực tế từ dữ liệu cào (ví dụ 35 phút = 2100s) và scale số lượng xe tương ứng.
"""

import sys
import math
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List, Optional

# Đảm bảo đường dẫn module luôn khả dụng
_SCRIPT_DIR = Path(__file__).resolve().parent
_MODULE_ROOT = _SCRIPT_DIR.parent
for p in [_SCRIPT_DIR, _MODULE_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Hỗ trợ Windows terminal encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    PROCESSED_DATA_DIR,
    NETWORK_XML_PATH,
    BASE_DIR
)

# ==============================================================================
# 1. THAM CHIẾU HỆ SỐ QUY ĐỔI XE CON (PCU) THEO TIÊU CHUẨN VIỆT NAM
# - TCVN 104:2007 (Đường đô thị - Yêu cầu thiết kế - Bảng 2)
# - TCVN 4054:2005 (Đường ô tô - Yêu cầu thiết kế - Bảng 3)
# - QCVN 07-4:2016/BXD (Quy chuẩn công trình giao thông đô thị)
# ==============================================================================
PCU_FACTORS = {
    "motorcycle": 0.30,      # Xe mô tô, xe gắn máy 2 bánh (TCVN 104:2007 quy định 0.30 cho đô thị đông)
    "passenger": 1.00,       # Xe con tiêu chuẩn (Base Unit)
    "bus": 2.00              # Xe buýt đô thị, xe khách trung bình
}

# ==============================================================================
# 2. BẢNG PHÂN TẦNG TỶ LỆ PHƯƠNG TIỆN (MODAL SPLIT) THEO CẤP ĐƯỜNG (HIGHWAY_TYPE)
# Đặc thù dòng xe tại TP.HCM: Trục lớn nhiều ô tô/buýt, đường nhánh/hẻm thuần xe máy.
# ==============================================================================
MODAL_SPLIT_BY_HIGHWAY = {
    # Đại lộ, cao tốc đô thị (Võ Văn Kiệt): Có làn ô tô riêng, xe cá nhân và buýt đông
    "motorway": {"motorcycle": 0.75, "passenger": 0.20, "bus": 0.05},
    "trunk":    {"motorcycle": 0.75, "passenger": 0.20, "bus": 0.05},
    
    # Trục chính đô thị (Điện Biên Phủ, Nguyễn Văn Cừ): Có tuyến buýt, nhiều taxi/xe con
    "primary":  {"motorcycle": 0.85, "passenger": 0.12, "bus": 0.03},
    "primary_link": {"motorcycle": 0.85, "passenger": 0.12, "bus": 0.03},

    # Đường chính khu vực / đường gom (Nguyễn Biểu, Nguyễn Cảnh Chân): Không có xe buýt, ít ô tô
    "secondary": {"motorcycle": 0.92, "passenger": 0.08, "bus": 0.00},
    "secondary_link": {"motorcycle": 0.92, "passenger": 0.08, "bus": 0.00},
    "tertiary":  {"motorcycle": 0.92, "passenger": 0.08, "bus": 0.00},
    "tertiary_link":  {"motorcycle": 0.92, "passenger": 0.08, "bus": 0.00},

    # Đường nội bộ, hẻm dân cư: Xe máy chiếm ưu thế tuyệt đối
    "residential":  {"motorcycle": 0.96, "passenger": 0.04, "bus": 0.00},
    "unclassified": {"motorcycle": 0.96, "passenger": 0.04, "bus": 0.00}
}

DEFAULT_MODAL_SPLIT = {"motorcycle": 0.85, "passenger": 0.12, "bus": 0.03}

def get_road_modal_split(highway_type: str) -> Dict[str, float]:
    """Lấy tỷ lệ phương tiện đặc thù theo cấp đường."""
    return MODAL_SPLIT_BY_HIGHWAY.get(str(highway_type).lower(), DEFAULT_MODAL_SPLIT)

def calculate_weighted_pcu(split: Dict[str, float]) -> float:
    """Tính hệ số quy đổi PCU trung bình của dòng xe trên tuyến đường."""
    return (
        split["motorcycle"] * PCU_FACTORS["motorcycle"] +
        split["passenger"]  * PCU_FACTORS["passenger"] +
        split["bus"]        * PCU_FACTORS["bus"]
    )

# ==============================================================================
# 3. THUẬT TOÁN ÁNH XẠ KHÔNG GIAN (SPATIAL MATCHING)
# Chiếu GPS (lat, lon) sang hệ tọa độ UTM Zone 48N của SUMO mạng lưới
# ==============================================================================
def latlon_to_utm48n(lat: float, lon: float) -> Tuple[float, float]:
    """Chuyển đổi tọa độ WGS84 (lat, lon) sang UTM Zone 48N (TP.HCM)."""
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1 - e2)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon0 = math.radians((48 - 1) * 6 - 180 + 3) # Kinh tuyến trục Zone 48 = 105 độ Đông

    N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
    T = math.tan(lat_rad)**2
    C = e_prime2 * math.cos(lat_rad)**2
    A = math.cos(lat_rad) * (lon_rad - lon0)
    M = a * ((1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * lat_rad
             - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat_rad)
             + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat_rad)
             - (35 * e2**3 / 3072) * math.sin(6 * lat_rad))
    k0 = 0.9996
    x = k0 * N * (A + (1 - T + C) * A**3 / 6 + (5 - 18 * T + T**2 + 72 * C - 58 * e_prime2) * A**5 / 120) + 500000.0
    y = k0 * (M + N * math.tan(lat_rad) * (A**2 / 2 + (5 - T + 9 * C + 4 * C**2) * A**4 / 24 + (61 - 58 * T + T**2 + 600 * C - 330 * e_prime2) * A**6 / 720))
    return x, y

def distance_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Khoảng cách Euclid ngắn nhất từ một điểm (px, py) tới đoạn thẳng (x1, y1) - (x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return math.hypot(px - closest_x, py - closest_y)

def distance_point_to_polyline(px: float, py: float, shape_points: List[Tuple[float, float]]) -> float:
    """Khoảng cách từ điểm tới chuỗi đa giác polyline (hình học của lane)."""
    if not shape_points:
        return float("inf")
    min_dist = float("inf")
    for i in range(len(shape_points) - 1):
        x1, y1 = shape_points[i]
        x2, y2 = shape_points[i + 1]
        dist = distance_point_to_segment(px, py, x1, y1, x2, y2)
        if dist < min_dist:
            min_dist = dist
    return min_dist

class SumoNetworkMatcher:
    """Trích xuất và quản lý hình học mạng lưới SUMO để thực hiện Spatial Matching."""
    def __init__(self, net_path: Path):
        self.net_path = net_path
        self.net_offset_x = 0.0
        self.net_offset_y = 0.0
        self.edges = {}       # edge_id -> list of (x, y) shape points
        self.way_to_edges = {} # base_way_id -> list of edge_ids
        self._load_network()

    def _load_network(self):
        print(f"[*] Dang phan tich mang luoi SUMO: {self.net_path}...")
        context = ET.iterparse(self.net_path, events=("end",))
        for event, elem in context:
            if elem.tag == "location":
                offsets = elem.attrib.get("netOffset", "0,0").split(",")
                self.net_offset_x = float(offsets[0])
                self.net_offset_y = float(offsets[1])
                elem.clear()
            elif elem.tag == "edge":
                if not elem.attrib.get("id", "").startswith(":"):
                    edge_id = elem.attrib["id"]
                    # Lấy hình học của làn đầu tiên
                    first_lane = elem.find("lane")
                    if first_lane is not None and "shape" in first_lane.attrib:
                        raw_shape = first_lane.attrib["shape"].strip().split()
                        shape_pts = []
                        for pt in raw_shape:
                            xy = pt.split(",")
                            shape_pts.append((float(xy[0]), float(xy[1])))
                        self.edges[edge_id] = shape_pts

                        # Gom nhóm theo OSM base way ID
                        clean_id = edge_id.lstrip("-+").split("#")[0]
                        self.way_to_edges.setdefault(clean_id, []).append(edge_id)
                elem.clear()
        print(f"[OK] Da nap {len(self.edges)} edges voi {len(self.way_to_edges)} base OSM ways.")

    def find_best_matching_edge(self, lat: float, lon: float, way_id_str: str) -> Optional[Tuple[str, float]]:
        """
        Tìm đoạn edge gần nhất với tọa độ (lat, lon) của điểm TomTom.
        Ưu tiên tìm trong các đoạn rẽ con (#0, #1, #2) của chính OSM way_id đó.
        """
        # 1. Chuyển lat, lon sang tọa độ mạng lưới SUMO (m)
        utm_x, utm_y = latlon_to_utm48n(lat, lon)
        sumo_x = utm_x + self.net_offset_x
        sumo_y = utm_y + self.net_offset_y

        clean_way_id = way_id_str.replace("way_", "").strip()

        # 2. Tìm danh sách các ứng viên (Candidate Edges)
        candidate_edge_ids = self.way_to_edges.get(clean_way_id, [])

        best_edge = None
        min_dist = float("inf")

        if candidate_edge_ids:
            # ƯU TIÊN 1: Tìm đoạn con (#0, #1, #2...) có khoảng cách gần nhất
            for eid in candidate_edge_ids:
                dist = distance_point_to_polyline(sumo_x, sumo_y, self.edges[eid])
                if dist < min_dist:
                    min_dist = dist
                    best_edge = eid
        else:
            # DỰ PHÒNG 2: Nếu way_id không khớp, quét tìm edge bất kỳ gần nhất trong bán kính 60m
            for eid, shape in self.edges.items():
                dist = distance_point_to_polyline(sumo_x, sumo_y, shape)
                if dist < min_dist and dist < 60.0:
                    min_dist = dist
                    best_edge = eid

        if best_edge:
            return best_edge, round(min_dist, 2)
        return None

# ==============================================================================
# 4. QUY TRÌNH CHUYỂN ĐỔI CHÍNH (MAIN WORKFLOW)
# ==============================================================================
def generate_sumo_counts(
    history_csv: Path,
    network_xml: Path,
    output_xml: Path,
    target_date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    alpha: float = 0.35,
    beta: float = 2.5,
    simulation_duration: Optional[int] = None
):
    print(f"\n==================================================")
    print(f"[*] BAT DAU CHUYEN DOI DU LIEU TOMTOM SANG SUMO EDGE COUNTS (alpha={alpha}, beta={beta})")
    print(f"==================================================")

    if not history_csv.exists():
        print(f"[!] Khong tim thay file: {history_csv}")
        return {}
    if not network_xml.exists():
        print(f"[!] Khong tim thay file: {network_xml}")
        return {}

    df = pd.read_csv(history_csv)
    print(f"[*] Doc duoc {len(df)} records tu file lich su crawl.")

    # 1. Xác định khung thời gian và lọc dữ liệu trước
    df["dt"] = pd.to_datetime(df["timestamp"])
    if target_date:
        df = df[df["date"] == target_date]
        if df.empty:
            print(f"[!] Khong co du lieu cho ngay {target_date}!")
            return {}

    if start_time:
        st = pd.to_datetime(start_time).time()
        df = df[df["dt"].dt.time >= st]
    if end_time:
        et = pd.to_datetime(end_time).time()
        df = df[df["dt"].dt.time <= et]

    if df.empty:
        print(f"[!] Khong co du lieu trong khung gio {start_time} -> {end_time}!")
        return {}

    # 2. Tự động tính toán lại lưu lượng BPR (Vectorized siêu tốc)
    if "current_travel_time_s" in df.columns and "free_flow_travel_time_s" in df.columns:
        t = pd.to_numeric(df["current_travel_time_s"], errors="coerce").fillna(0).values
        t0 = pd.to_numeric(df["free_flow_travel_time_s"], errors="coerce").fillna(1).values
        cap = pd.to_numeric(df["road_capacity_pcu"] if "road_capacity_pcu" in df.columns else 1200.0, errors="coerce").fillna(1200.0).values

        ratio = np.maximum(0.0, (t - t0) / np.maximum(1e-3, alpha * t0))
        vol = np.where(t <= t0, 0.05 * cap, cap * np.power(ratio, 1.0 / beta))
        df["est_volume_vph"] = np.nan_to_num(vol, nan=0.0)
        df["arrival_rate_vps"] = (df["est_volume_vph"] / 3600.0).round(4)

    min_time = df["dt"].min()
    max_time = df["dt"].max()
    if simulation_duration is not None and simulation_duration > 0:
        time_diff_seconds = int(simulation_duration)
    else:
        time_diff_seconds = max(300, int((max_time - min_time).total_seconds()))

    print(f"[*] Khoang thoi gian du lieu: {min_time.strftime('%H:%M:%S')} -> {max_time.strftime('%H:%M:%S')}")
    print(f"[*] Thoi luong mo phong tu dong: {time_diff_seconds} giay (~{time_diff_seconds // 60} phut)")

    # 2. Gom nhóm theo point_id và lấy lưu lượng trung bình trong khoảng thời gian này
    grouped = df.groupby("point_id").agg({
        "road_name": "first",
        "highway_type": "first",
        "lat": "first",
        "lon": "first",
        "lanes": "first",
        "est_volume_vph": "mean"
    }).reset_index()

    print(f"[*] Tong so diem do doc lap can map: {len(grouped)} diem.")

    # 3. Khởi tạo bộ nạp mạng lưới SUMO để Spatial Matching
    matcher = SumoNetworkMatcher(network_xml)

    # 4. Tính toán số xe thực tế và ánh xạ không gian
    mapped_records = []
    skipped_count = 0

    scale_factor = time_diff_seconds / 3600.0  # Tỷ lệ scale từ 1h về thời lượng mô phỏng

    print(f"\n[*] Dang thuc hien Spatial Matching va quy doi PCU:")
    for _, row in grouped.iterrows():
        p_id = row["point_id"]
        r_name = row["road_name"]
        h_type = row["highway_type"]
        lat = float(row["lat"])
        lon = float(row["lon"])
        vol_pcu = float(row["est_volume_vph"])

        # Tìm edge chính xác nhất bằng Spatial Matching
        match_result = matcher.find_best_matching_edge(lat, lon, p_id)
        if not match_result:
            print(f"  [X] Bo qua {r_name} ({p_id}): Khong tim thay edge phu hop trong SUMO net.")
            skipped_count += 1
            continue

        best_edge_id, dist_m = match_result

        # Tính toán tỷ lệ phương tiện đặc thù theo cấp đường
        modal_split = get_road_modal_split(h_type)
        weighted_pcu = calculate_weighted_pcu(modal_split)

        # Quy đổi từ PCU sang số xe thực tế (Vehicles / hour)
        n_physical_vph = vol_pcu / weighted_pcu

        # Tính số xe mục tiêu trong khoảng thời lượng mô phỏng (ví dụ 35 phút)
        target_count_interval = int(round(n_physical_vph * scale_factor))

        mapped_records.append({
            "edge_id": best_edge_id,
            "road_name": r_name,
            "distance_m": dist_m,
            "highway_type": h_type,
            "vol_pcu_vph": round(vol_pcu, 1),
            "weighted_pcu": round(weighted_pcu, 3),
            "physical_vph": round(n_physical_vph, 1),
            "target_count": target_count_interval
        })

        print(f"  [OK] {r_name} ({p_id}) -> Edge '{best_edge_id}' (kc={dist_m}m) | "
              f"PCU={vol_pcu:.0f} -> Xe Thuc={n_physical_vph:.0f} vph -> Muc tieu {time_diff_seconds//60}p: {target_count_interval} xe")

    # 5. Xuất file XML chuẩn theo schema của SUMO edgeData
    output_xml.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("data")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/datamode_file.xsd")

    interval = ET.SubElement(root, "interval")
    interval.set("id", "tomtom_measured_flows")
    interval.set("begin", "0")
    interval.set("end", str(time_diff_seconds))

    for rec in mapped_records:
        edge_elem = ET.SubElement(interval, "edge")
        edge_elem.set("id", rec["edge_id"])
        edge_elem.set("entered", str(rec["target_count"]))

    # Ghi định dạng XML có thụt dòng đẹp
    ET.indent(root, space="    ", level=0)
    tree = ET.ElementTree(root)
    tree.write(output_xml, encoding="utf-8", xml_declaration=True)

    print(f"\n==================================================")
    print(f"[OK] HOAN TAT! Da xuat file edge_counts.xml vao:")
    print(f"     --> {output_xml}")
    print(f"[*] Thong ke:")
    print(f"    - So diem map thanh cong: {len(mapped_records)}/{len(grouped)}")
    print(f"    - So diem bo qua (khong co trong net): {skipped_count}")
    print(f"    - Thoi luong mo phong duoc cau hinh: {time_diff_seconds}s ({time_diff_seconds//60} phut)")
    print(f"    - Tong luong xe muc tieu can nap vao mo phong: {sum(r['target_count'] for r in mapped_records):,} xe")
    print(f"==================================================")
    
    # Trả về dictionary lưu lượng mục tiêu quy đổi theo giờ (veh/h) cho từng edge để tính GEH
    target_hourly_dict = {rec["edge_id"]: rec["physical_vph"] for rec in mapped_records}
    return target_hourly_dict

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert TomTom CSV to SUMO edge_counts.xml")
    parser.add_argument("--input", "-i", type=str, default=str(PROCESSED_DATA_DIR / "macro_traffic_dense_1min.csv"),
                        help="Đường dẫn file CSV đầu vào (mặc định: macro_traffic_dense_1min.csv)")
    parser.add_argument("--output", "-o", type=str, default=str(PROCESSED_DATA_DIR / "edge_counts.xml"),
                        help="Đường dẫn file XML đầu ra (mặc định: edge_counts.xml)")
    parser.add_argument("--date", "-d", type=str, default=None,
                        help="Lọc theo ngày cụ thể (YYYY-MM-DD)")
    parser.add_argument("--start-time", "-s", type=str, default=None,
                        help="Giờ bắt đầu (HH:MM hoặc HH:MM:SS, ví dụ: 17:00)")
    parser.add_argument("--end-time", "-e", type=str, default=None,
                        help="Giờ kết thúc (HH:MM hoặc HH:MM:SS, ví dụ: 18:00)")
    parser.add_argument("--alpha", type=float, default=0.35,
                        help="Tham số alpha của hàm BPR (mặc định: 0.35)")
    parser.add_argument("--beta", type=float, default=2.5,
                        help="Tham số beta của hàm BPR (mặc định: 2.5)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        fallback = PROCESSED_DATA_DIR / "macro_traffic_history.csv"
        if fallback.exists():
            print(f"[!] Không tìm thấy {input_path}, tự động chuyển sang file: {fallback}")
            input_path = fallback

    generate_sumo_counts(
        history_csv=input_path,
        network_xml=NETWORK_XML_PATH,
        output_xml=Path(args.output),
        target_date=args.date,
        start_time=args.start_time,
        end_time=args.end_time,
        alpha=args.alpha,
        beta=args.beta
    )
