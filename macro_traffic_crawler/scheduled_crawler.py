"""
scheduled_crawler.py
Hệ thống Crawler Tự động Lên lịch & Xoay vòng Nhiều API Keys:
1. Khung giờ quét cố định trong ngày:
   - 06:00 - 08:00 (Sáng cao điểm)
   - 10:00 - 12:00 (Trưa bình thường)
   - 16:00 - 18:00 (Chiều cao điểm)
   - 02:00 - 03:00 (Đêm vắng)
2. Quản lý xoay vòng 5 API Keys: Tự động chuyển đổi mượt mà khi hết quota.
3. Tự động tính năng lực (C) theo TCVN 104:2007 và BPR flow.
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
from config import (
    POINTS_FILE,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    STATE_FILE,
    TOMTOM_API_KEYS,
    CRAWL_INTERVAL_SECONDS,
    REQUEST_DELAY_SECONDS
)
from tomtom_client import TomTomTrafficClient, QuotaExceededError
from key_rotator import KeyRotator
from run_crawler import calculate_segment_capacity, estimate_bpr_volume

# ==============================================================================
# CẤU HÌNH CÁC KHUNG GIỜ CỐ ĐỊNH (SCHEDULE WINDOWS)
# ==============================================================================
SCHEDULE_WINDOWS = [
    {"name": "Sáng cao điểm",   "start": dtime(6, 0),  "end": dtime(8, 0)},
    {"name": "Trưa bình thường", "start": dtime(10, 0), "end": dtime(12, 0)},
    {"name": "Chiều cao điểm",  "start": dtime(16, 0), "end": dtime(18, 0)},
    {"name": "Đêm vắng vẻ",     "start": dtime(2, 0),  "end": dtime(3, 0)}
]

def check_schedule_window(now: datetime) -> Tuple[bool, Optional[str], int]:
    """
    Kiểm tra thời điểm hiện tại có nằm trong các khung giờ cào hay không.
    Trả về:
    - in_window (bool): True nếu đang trong khung giờ.
    - current_window_name (str): Tên khung giờ hiện tại (nếu có).
    - seconds_to_next (int): Số giây còn lại cho đến khung giờ kế tiếp.
    """
    curr_time = now.time()

    # 1. Kiểm tra xem có đang nằm trong khung giờ nào không
    for win in SCHEDULE_WINDOWS:
        if win["start"] <= curr_time < win["end"]:
            return True, win["name"], 0

    # 2. Nếu không, tính thời gian cần ngủ đến khung giờ gần nhất tiếp theo
    now_ts = now.timestamp()
    candidates = []

    for win in SCHEDULE_WINDOWS:
        # Giờ bắt đầu trong ngày hôm nay
        start_today = datetime.combine(now.date(), win["start"])
        if start_today > now:
            candidates.append(start_today)
        else:
            # Giờ bắt đầu vào ngày mai
            start_tomorrow = datetime.combine(now.date() + timedelta(days=1), win["start"])
            candidates.append(start_tomorrow)

    next_window_time = min(candidates)
    seconds_to_wait = int(next_window_time.timestamp() - now_ts)
    return False, None, max(1, seconds_to_wait)

def run_scheduled_crawl_round(client: TomTomTrafficClient, rotator: KeyRotator, points_file: Path, limit: int = None):
    """Thực hiện trọn vẹn 1 vòng cào cho toàn bộ danh sách điểm đo có failover API key."""
    if not points_file.exists():
        print(f"[!] Khong tim thay {points_file}. Vui long chay extract_osm_points.py truoc.")
        return False

    df_points = pd.read_csv(points_file)
    if limit:
        df_points = df_points.head(limit)

    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    iso_time_str = now.isoformat()

    print(f"\n==================================================")
    print(f"[*] Bat dau vong cào: {iso_time_str} | Tong so diem: {len(df_points)}")
    print(f"==================================================")

    raw_snapshots = []
    processed_records = []

    for idx, row in df_points.iterrows():
        point_id = row["point_id"]
        road_name = row["road_name"]
        lat = float(row["lat"])
        lon = float(row["lon"])
        lanes = int(row.get("lanes", 1))

        # Cơ chế In-flight Key Failover: Thử lấy key khả dụng
        flow = None
        while flow is None:
            active_key = rotator.get_active_key()
            if not active_key:
                print("[ALERT] Tat ca cac API keys da can kiet quota. Dung vong crawl.")
                return False

            try:
                flow = client.get_flow_segment(lat, lon, api_key=active_key)
                if flow:
                    rotator.record_success(active_key)
                else:
                    break # Lỗi dữ liệu khác, bỏ qua điểm này
            except QuotaExceededError:
                # Key bị hết quota ngay lập tức -> Đánh dấu và tự động lấy key tiếp theo
                rotator.mark_exhausted(active_key, reason="TomTom tra ve 403 Quota Exceeded")
                print(f"[*] Chuyen ngay sang API key tiep theo cho diem {point_id}...")

        if not flow:
            continue

        raw_snapshots.append({
            "point_id": point_id,
            "road_name": road_name,
            "lat": lat,
            "lon": lon,
            "lanes": lanes,
            "timestamp": iso_time_str,
            "data": flow.get("raw_response", {})
        })

        # Tính toán đặc trưng vĩ mô chuẩn TCVN
        curr_t = flow["current_travel_time"]
        free_t = flow["free_flow_travel_time"]
        frc_code = flow.get("frc", "FRC1")
        segment_cap = calculate_segment_capacity(frc_code, lanes)
        est_volume = estimate_bpr_volume(curr_t, free_t, capacity=segment_cap)
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
            "lanes": lanes,
            "frc": frc_code,
            "road_capacity_pcu": segment_cap,
            "current_speed_kmh": flow["current_speed"],
            "free_flow_speed_kmh": flow["free_flow_speed"],
            "current_travel_time_s": curr_t,
            "free_flow_travel_time_s": free_t,
            "delay_s": flow["delay_seconds"],
            "congestion_index": flow["congestion_index"],
            "confidence": flow["confidence"],
            "road_closure": flow["road_closure"],
            "est_volume_vph": est_volume,
            "arrival_rate_vps": arrival_rate_vps
        })

        print(f"  [{idx+1}/{len(df_points)}] {road_name} ({point_id}): "
              f"Lanes={lanes}, Speed={flow['current_speed']:.1f}/{flow['free_flow_speed']:.1f} km/h, "
              f"Vol={est_volume:.0f} vph")

    # 1. Lưu RAW JSON Snapshot
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_file = RAW_DATA_DIR / f"raw_snapshot_{timestamp_str}.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_snapshots, f, ensure_ascii=False, indent=2)

    # 2. Lưu PROCESSED CSV History
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    # processed_file = PROCESSED_DATA_DIR / "macro_traffic_history.csv"
    processed_file = PROCESSED_DATA_DIR / "macro_traffic_dense_1min.csv"
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
    print(f"[OK] Da luu thanh cong {len(processed_records)} records vao: {processed_file}")
    return True

def main():
    parser = argparse.ArgumentParser(description="TomTom Multi-Key Scheduled Macro Traffic Crawler")
    parser.add_argument("--now", action="store_true", help="Bo qua kiem tra gio, chay ngay lap tuc 1 vong (dung de test)")
    parser.add_argument("--all-day", action="store_true", help="Chay lien tuc 24/24 khong gioi han theo 4 khung gio co dinh")
    parser.add_argument("--mock", action="store_true", help="Chay o che do Mock Test voi 5 keys ao")
    parser.add_argument("--interval", type=int, default=CRAWL_INTERVAL_SECONDS, help="Khoang cach giua cac vong trong khung gio (giay)")
    parser.add_argument("--limit", type=int, default=None, help="Gioi han so diem do moi vong")
    parser.add_argument("--summary", action="store_true", help="Chi in thong ke quota cac keys roi thoat")

    args = parser.parse_args()

    # Khoi tao bo quan ly xoay vong keys
    rotator = KeyRotator(
        keys=TOMTOM_API_KEYS,
        state_file=STATE_FILE,
        mock_mode=args.mock or len(TOMTOM_API_KEYS) == 0
    )

    if args.summary:
        rotator.print_summary()
        return

    client = TomTomTrafficClient(api_key="MOCK" if args.mock else None)

    print("==================================================")
    print("[*] KHOI DONG HE THONG CRAWLER NHIEU KEYS & LEN LICH")
    print(f"[*] Tong so API Keys duoc nap: {len(rotator.keys)}")
    if args.all_day:
        print("[*] CHE DO: Cào liên tục 24/24 (Không giới hạn khung giờ)")
    else:
        print(f"[*] Cac khung gio quan trac trong ngay:")
        for win in SCHEDULE_WINDOWS:
            print(f"    + {win['name']}: {win['start'].strftime('%H:%M')} -> {win['end'].strftime('%H:%M')}")
    print("==================================================")
    rotator.print_summary()

    if args.now:
        print("[*] Che do '--now': Chay kiem tra ngay 1 vong cào...")
        run_scheduled_crawl_round(client, rotator, POINTS_FILE, limit=args.limit)
        rotator.print_summary()
        return

    try:
        while True:
            now = datetime.now()
            if args.all_day:
                in_window = True
                window_name = "Toan bo 24h"
                seconds_to_wait = 0
            else:
                in_window, window_name, seconds_to_wait = check_schedule_window(now)

            if in_window:
                print(f"\n[DANG TRONG KHUNG GIO] >>> {window_name} ({now.strftime('%H:%M:%S')}) <<<")
                success = run_scheduled_crawl_round(client, rotator, POINTS_FILE, limit=args.limit)
                
                if not success:
                    # Nếu hết toàn bộ keys, ngủ đến 07:05 sáng mai để chờ reset
                    print("[!] Dung crawler cho den khi reset quota vao 07:05 sang mai.")
                    time.sleep(3600)
                    continue

                rotator.print_summary()
                print(f"[*] Hoan thanh 1 vong. Nghi {args.interval} giay truoc khi cào tiep...")
                time.sleep(args.interval)

            else:
                next_time_str = (now + timedelta(seconds=seconds_to_wait)).strftime('%H:%M:%S %d/%m')
                print(f"[*] Hien tai ngoai khung gio cào ({now.strftime('%H:%M:%S')}).")
                print(f"[*] He thong se 'ngu' {seconds_to_wait // 60} phut ({seconds_to_wait}s) den khung gio tiep theo: {next_time_str}...")
                
                # Ngu chia nho theo từng phút để có thể bắt Ctrl+C mượt mà
                sleep_chunk = min(60, seconds_to_wait)
                time.sleep(sleep_chunk)

    except KeyboardInterrupt:
        print("\n[*] Nguoi dung da dung tien trinh crawler.")
        rotator.print_summary()

if __name__ == "__main__":
    main()
