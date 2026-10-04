"""
run_crawler.py
Pipeline thu thap Macro Traffic Data tu TomTom:
1. Doc danh sach diem do tu data/sampling_points.csv
2. Goi TomTom Traffic Flow API
3. Luu Snapshot Raw JSON vao data/raw/
4. Luu Bang dac trung vi mo chuan hoa vao data/processed/macro_traffic_history.csv
5. Tinh toan san cac feature tien de cho buoc Micro hoa (BPR flow & arrival rate).
"""

import sys
import os
import json
import time
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path

# Dam bao encoding ho tro Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    POINTS_FILE,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    CRAWL_INTERVAL_SECONDS
)
from tomtom_client import TomTomTrafficClient

def estimate_bpr_volume(current_time: float, free_time: float, capacity: float = 1200.0, alpha: float = 0.15, beta: float = 4.0) -> float:
    """
    Uoc tinh luu luong xe (vehicles/hour) dua tren ham BPR (Bureau of Public Roads):
    T = T_0 * (1 + alpha * (V/C)^beta)
    => V = C * ((T / T_0 - 1) / alpha) ^ (1/beta)
    """
    if free_time <= 0 or current_time <= free_time:
        return 0.0
    ratio = current_time / free_time
    if ratio <= 1.0:
        return 0.0
    try:
        term = (ratio - 1.0) / alpha
        if term < 0:
            return 0.0
        v_c = term ** (1.0 / beta)
        volume = capacity * v_c
        return round(min(volume, capacity * 2.0), 1)
    except Exception:
        return 0.0

def run_snapshot_collection(client: TomTomTrafficClient, points_file: Path, limit: int = None):
    if not points_file.exists():
        print(f"[!] Khong tim thay {points_file}. Vui long chay extract_osm_points.py truoc.")
        return

    df_points = pd.read_csv(points_file)
    if limit:
        df_points = df_points.head(limit)

    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    iso_time_str = now.isoformat()

    print(f"\n==================================================")
    print(f"[*] Bat dau thu thap snapshot macro data: {iso_time_str}")
    print(f"[*] Tong so diem do: {len(df_points)}")
    print(f"==================================================")

    raw_snapshots = []
    processed_records = []

    for idx, row in df_points.iterrows():
        point_id = row["point_id"]
        road_name = row["road_name"]
        lat = float(row["lat"])
        lon = float(row["lon"])

        flow = client.get_flow_segment(lat, lon)
        if not flow:
            continue

        raw_snapshots.append({
            "point_id": point_id,
            "road_name": road_name,
            "lat": lat,
            "lon": lon,
            "timestamp": iso_time_str,
            "data": flow.get("raw_response", {})
        })

        # Tinh toan feature vi mo cho Micro hoa
        curr_t = flow["current_travel_time"]
        free_t = flow["free_flow_travel_time"]
        est_volume = estimate_bpr_volume(curr_t, free_t, capacity=1200.0)
        arrival_rate_vps = round(est_volume / 3600.0, 4)

        processed_records.append({
            "timestamp": iso_time_str,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "point_id": point_id,
            "road_name": road_name,
            "highway_type": row.get("highway_type", "primary"),
            "lat": lat,
            "lon": lon,
            "frc": flow["frc"],
            "current_speed_kmh": flow["current_speed"],
            "free_flow_speed_kmh": flow["free_flow_speed"],
            "current_travel_time_s": curr_t,
            "free_flow_travel_time_s": free_t,
            "delay_s": flow["delay_seconds"],
            "congestion_index": flow["congestion_index"],
            "confidence": flow["confidence"],
            "road_closure": flow["road_closure"],
            # Cac features quan trong nhat de sinh xe trong SUMO/CityFlow:
            "est_volume_vph": est_volume,
            "arrival_rate_vps": arrival_rate_vps
        })

        print(f"  [{idx+1}/{len(df_points)}] {road_name} ({point_id}): "
              f"Speed={flow['current_speed']}/{flow['free_flow_speed']} km/h, "
              f"Delay={flow['delay_seconds']}s, Congestion={flow['congestion_index']*100:.1f}%")

    # 1. Luu RAW JSON snapshot
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_file = RAW_DATA_DIR / f"raw_snapshot_{timestamp_str}.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_snapshots, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Da luu Raw Snapshot vao: {raw_file}")

    # 2. Luu PROCESSED CSV history
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    processed_file = PROCESSED_DATA_DIR / "macro_traffic_history.csv"
    df_new = pd.DataFrame(processed_records)

    if processed_file.exists() and os.path.getsize(processed_file) > 0:
        try:
            df_existing = pd.read_csv(processed_file)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new

    df_combined.to_csv(processed_file, index=False, encoding="utf-8-sig")
    print(f"[OK] Da cap nhat bang Macro Features vao: {processed_file} (Tong dong: {len(df_combined)})")

def main():
    parser = argparse.ArgumentParser(description="TomTom Macro Traffic Data Collector")
    parser.add_argument("--mode", choices=["once", "loop"], default="once", help="Che do chay: 'once' (1 lan) hoac 'loop' (dinh ky)")
    parser.add_argument("--interval", type=int, default=CRAWL_INTERVAL_SECONDS, help="Khoang thoi gian lap lai giua cac vong (giay)")
    parser.add_argument("--limit", type=int, default=10, help="Gioi han so diem do crawl moi vong (mac dinh 10 de tiet kiem quota)")
    parser.add_argument("--mock", action="store_true", help="Ep buoc chay che do Mock data (khong ton API quota)")

    args = parser.parse_args()

    client = TomTomTrafficClient(api_key="MOCK" if args.mock else None)

    if args.mode == "once":
        run_snapshot_collection(client, POINTS_FILE, limit=args.limit)
    else:
        print(f"[*] Bat dau che do lap dinh ky moi {args.interval} giay. Nhan Ctrl+C de dung.")
        try:
            while True:
                run_snapshot_collection(client, POINTS_FILE, limit=args.limit)
                print(f"[*] Nghi {args.interval} giay cho vong crawl tiep theo...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[*] Da dung qua trinh crawl dinh ky.")

if __name__ == "__main__":
    main()
