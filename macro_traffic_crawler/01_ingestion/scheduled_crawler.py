"""
scheduled_crawler.py
Hệ thống Crawler Tự động Lên lịch & Quản lý Hạn ngạch Thông minh (Smart Quota Guard):
1. Chế độ Cào Liên tục & Tùy biến chu kỳ (Custom Interval):
   - Mặc định cào liên tục với chu kỳ tùy chỉnh (--interval 60 -> chu kỳ thực tế ~120s do độ trễ 66 điểm).
2. Cơ chế Quota Guard (Ví dự phòng sáng sớm):
   - Mặc định bảo lưu 3.000 requests (hoặc tùy biến qua --reserve 3000) cho khung 06:00 - 07:00 sáng hôm sau.
   - Khi hết hạn ngạch ban ngày (21.800 reqs đã tiêu thụ), hệ thống tự động đi ngủ (Sleep) qua đêm để bảo toàn quota.
   - Đúng 06:00:00 sáng hôm sau, tự động thức dậy, mở khóa 3.000 requests cào tiếp đến khi TomTom reset lúc 07:00:00.
   - Lúc 07:00:00 sáng (00:00 UTC), TomTom reset hạn ngạch mới 100%, vòng lặp lại tiếp tục mượt mà.
3. Cơ chế Windows Keep-Awake:
   - Tự động ngăn Windows rơi vào trạng thái Sleep/Hibernate khi script đang chạy ngầm.
"""

import sys
import os
import json
import time
import ctypes
import argparse
from datetime import datetime, timezone, timedelta, time as dtime
from pathlib import Path
from typing import List, Tuple, Optional

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo import config, tomtom_client, key_rotator, run_crawler
_SCRIPT_DIR = Path(__file__).resolve().parent
_MODULE_ROOT = _SCRIPT_DIR.parent
for p in [_SCRIPT_DIR, _MODULE_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

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
from key_rotator import KeyRotator, VN_TZ
from run_crawler import calculate_segment_capacity, estimate_bpr_volume

# ==============================================================================
# HỖ TRỢ WINDOWS KEEP-AWAKE (CHỐNG NGỦ MÁY)
# ==============================================================================
def set_windows_keep_awake(enable: bool = True):
    """Bật/tắt cờ ngăn Windows rơi vào trạng thái Sleep/Hibernate khi cào dữ liệu dài hạn."""
    if sys.platform == "win32":
        try:
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_AWAYMODE_REQUIRED = 0x00000040
            if enable:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                )
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception:
            pass

# ==============================================================================
# CÁC HÀM TÍNH TOÁN THỜI GIAN CHỜ THÔNG MINH
# ==============================================================================
def get_seconds_until_next_target(target_hour: int, target_minute: int = 0) -> Tuple[int, datetime]:
    """Tính số giây từ thời điểm hiện tại đến mốc giờ mục tiêu kế tiếp theo giờ VN."""
    now_vn = datetime.now(VN_TZ)
    target_today = now_vn.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    if now_vn < target_today:
        target_time = target_today
    else:
        target_time = target_today + timedelta(days=1)
        
    seconds_to_wait = int((target_time - now_vn).total_seconds())
    return max(1, seconds_to_wait), target_time

def sleep_countdown(seconds: int, reason_msg: str):
    """Ngủ ngắt quãng theo từng 15-30 giây để bắt tín hiệu Ctrl+C mượt mà."""
    print(f"\n[*] {reason_msg}")
    end_time = time.time() + seconds
    try:
        while time.time() < end_time:
            remaining = int(end_time - time.time())
            if remaining <= 0:
                break
            hrs = remaining // 3600
            mins = (remaining % 3600) // 60
            secs = remaining % 60
            # Cập nhật dòng trạng thái trên cùng 1 dòng
            sys.stdout.write(f"\r  [SLEEP MODE] Còn lại: {hrs:02d}h {mins:02d}m {secs:02d}s ...   ")
            sys.stdout.flush()
            time.sleep(min(15, remaining))
        print("\n[*] Đã hết thời gian chờ. Thức dậy tiếp tục tiến trình!\n")
    except KeyboardInterrupt:
        print("\n\n[*] Người dùng hủy bỏ thời gian chờ.")
        raise

# ==============================================================================
# VÒNG CÀO 1 SNAPSHOT CHO TOÀN BỘ CÁC ĐIỂM ĐO
# ==============================================================================
def run_scheduled_crawl_round(
    client: TomTomTrafficClient,
    rotator: KeyRotator,
    points_file: Path,
    limit: Optional[int] = None,
    output_csv: Optional[str] = None,
    save_raw: bool = False
) -> bool:
    """Thực hiện trọn vẹn 1 vòng cào cho toàn bộ danh sách điểm đo có failover API key."""
    if not points_file.exists():
        print(f"[!] Không tìm thấy file {points_file}. Vui lòng tạo danh sách điểm trước.")
        return False

    df_points = pd.read_csv(points_file)
    if limit:
        df_points = df_points.head(limit)

    now_vn = rotator.get_vn_now()
    timestamp_str = now_vn.strftime("%Y%m%d_%H%M%S")
    iso_time_str = now_vn.isoformat()

    print(f"\n==================================================")
    print(f"[*] Bắt đầu vòng cào: {now_vn.strftime('%H:%M:%S %d/%m/%Y')} | Điểm đo: {len(df_points)}")
    print(f"==================================================")

    raw_snapshots = []
    processed_records = []
    t_round_start = time.time()

    for idx, row in df_points.iterrows():
        point_id = row["point_id"]
        road_name = row["road_name"]
        lat = float(row["lat"])
        lon = float(row["lon"])
        lanes = int(row.get("lanes", 1))

        # Cơ chế Failover Key tức thời khi gặp lỗi hoặc chạm trần
        flow = None
        while flow is None:
            active_key = rotator.get_active_key()
            if not active_key:
                print(f"[!] Tạm dừng cào giữa vòng tại điểm #{idx+1} do chính sách Quota Guard.")
                return False

            try:
                flow = client.get_flow_segment(lat, lon, api_key=active_key)
                if flow:
                    rotator.record_success(active_key)
                else:
                    break
            except QuotaExceededError:
                rotator.mark_exhausted(active_key, reason="TomTom báo HTTP 403 Quota Exceeded")
                print(f"[*] Chuyển ngay sang API key tiếp theo cho điểm {point_id}...")

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

        curr_t = flow["current_travel_time"]
        free_t = flow["free_flow_travel_time"]
        frc_code = flow.get("frc", "FRC1")
        segment_cap = calculate_segment_capacity(frc_code, lanes)
        est_volume = estimate_bpr_volume(curr_t, free_t, capacity=segment_cap)
        arrival_rate_vps = round(est_volume / 3600.0, 4)

        processed_records.append({
            "timestamp": iso_time_str,
            "date": now_vn.strftime("%Y-%m-%d"),
            "time": now_vn.strftime("%H:%M:%S"),
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

        print(f"  [{idx+1:02d}/{len(df_points)}] {road_name} ({point_id}): "
              f"Speed={flow['current_speed']:.1f}/{flow['free_flow_speed']:.1f} km/h, Conf={flow['confidence']:.2f}")

    round_duration = time.time() - t_round_start
    print(f"[*] Vòng cào hoàn tất trong: {round_duration:.1f} giây ({len(processed_records)}/{len(df_points)} điểm thành công)")

    # 1. Lưu RAW JSON Snapshot (nếu được bật)
    if save_raw and raw_snapshots:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        raw_file = RAW_DATA_DIR / f"raw_snapshot_{timestamp_str}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(raw_snapshots, f, ensure_ascii=False, indent=2)

    # 2. Ghi nối tiếp vào file PROCESSED CSV
    if processed_records:
        if output_csv:
            out_p = Path(output_csv)
            processed_file = (PROCESSED_DATA_DIR / out_p) if len(out_p.parts) == 1 else out_p
        else:
            processed_file = PROCESSED_DATA_DIR / "macro_traffic_history.csv"
            
        processed_file.parent.mkdir(parents=True, exist_ok=True)
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
        print(f"[OK] Đã lưu nối tiếp {len(processed_records)} records vào: {processed_file}")

    return True

# ==============================================================================
# HÀM CHÍNH (MAIN SCHEDULER & RUNNER)
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="TomTom Smart Quota Guard Continuous Traffic Crawler")
    parser.add_argument("--now", action="store_true", help="Chạy ngay lập tức 1 vòng kiểm tra rồi thoát")
    parser.add_argument("--all-day", action="store_true", help="Chạy liên tục cả ngày (tương thích ngược)")
    parser.add_argument("--interval", type=int, default=60, help="Thời gian nghỉ giữa các vòng cào (giây, mặc định 60s)")
    parser.add_argument("--reserve", type=int, default=3000, help="Số lượng request bảo lưu tuyệt đối cho khung 06:00 - 07:00 sáng mai (mặc định 3.000 reqs)")
    parser.add_argument("--morning-start", type=int, default=6, help="Giờ mở khóa ví dự phòng vào sáng sớm hôm sau (mặc định 6 = 06:00 AM)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số điểm đo mỗi vòng (dùng để test nhanh)")
    parser.add_argument("--output", "-o", type=str, default="macro_traffic_history.csv", help="File CSV đầu ra (mặc định: macro_traffic_history.csv)")
    parser.add_argument("--save-raw", action="store_true", help="Lưu file JSON raw snapshot của từng vòng")
    parser.add_argument("--summary", action="store_true", help="Chỉ in thống kê quota của các keys rồi thoát")
    parser.add_argument("--reset", action="store_true", help="Buộc reset toàn bộ trạng thái quota về 0 ngay lập tức")
    parser.add_argument("--mock", action="store_true", help="Chạy ở chế độ Mock Test (không tốn request TomTom thật)")

    args = parser.parse_args()

    # Kích hoạt chế độ chống ngủ máy Windows
    set_windows_keep_awake(True)

    # Khởi tạo bộ quản lý xoay vòng keys với cơ chế Quota Guard
    rotator = KeyRotator(
        keys=TOMTOM_API_KEYS,
        state_file=STATE_FILE,
        reserve_requests=args.reserve,
        morning_start_hour=args.morning_start,
        mock_mode=args.mock or len(TOMTOM_API_KEYS) == 0
    )

    if args.reset:
        rotator.force_reset()
        rotator.print_summary()
        set_windows_keep_awake(False)
        return

    if args.summary:
        rotator.print_summary()
        set_windows_keep_awake(False)
        return

    client = TomTomTrafficClient(api_key="MOCK" if args.mock else None)

    print("=================================================================")
    print("[*] HỆ THỐNG CRAWLER TOMTOM TỰ ĐỘNG - SMART QUOTA GUARD")
    print(f"[*] Số lượng API Keys: {len(rotator.keys)} | Tổng dung lượng Pool: {rotator.get_total_capacity()} reqs")
    print(f"[*] Ngưỡng bảo lưu sáng hôm sau: {args.reserve} reqs (dành riêng cho khung 06:00 - 07:00)")
    print(f"[*] Chu kỳ nghỉ giữa các vòng: {args.interval} giây")
    print(f"[*] Tệp dữ liệu đầu ra: {args.output}")
    print(f"[*] Cơ chế Windows Keep-Awake: ĐÃ BẬT (Ngăn máy tính tự Sleep/Hibernate)")
    print("=================================================================")
    rotator.print_summary()

    if args.now:
        print("[*] Chế độ '--now': Chạy ngay 1 vòng kiểm tra kỹ thuật...")
        run_scheduled_crawl_round(client, rotator, POINTS_FILE, limit=args.limit, output_csv=args.output, save_raw=args.save_raw)
        rotator.print_summary()
        set_windows_keep_awake(False)
        return

    try:
        while True:
            # Kiểm tra và xử lý reset hạn ngạch ngày mới lúc 07:00 AM VN (00:00 UTC)
            rotator.check_utc_day_reset()

            active_key = rotator.get_active_key()

            if active_key is not None:
                # Có key khả dụng -> Thực hiện 1 vòng cào
                success = run_scheduled_crawl_round(
                    client=client,
                    rotator=rotator,
                    points_file=POINTS_FILE,
                    limit=args.limit,
                    output_csv=args.output,
                    save_raw=args.save_raw
                )

                if success:
                    print(f"[*] Nghỉ {args.interval}s trước khi bước vào vòng cào kế tiếp...")
                    time.sleep(args.interval)
                else:
                    # Đang cào mà hết key / chạm ngưỡng quota guard
                    time.sleep(5)
            else:
                # Quota Guard kích hoạt hoặc toàn bộ keys đã cạn kiệt
                rotator.print_summary()
                now_vn = rotator.get_vn_now()

                if rotator.is_morning_reserve_window():
                    # Đang trong khung 06:00 - 07:00 mà hết key -> Ngủ đến 07:00:05 để chờ TomTom reset
                    secs_to_wait, target_time = get_seconds_until_next_target(7, 0)
                    msg = f"Đã dùng hết quỹ dự phòng sáng sớm. Ngủ đến thời điểm reset {target_time.strftime('%H:%M:%S')}..."
                else:
                    # Ban ngày đã chạm ngưỡng bảo lưu 3.000 reqs -> Ngủ qua đêm đến đúng 06:00:00 sáng mai
                    secs_to_wait, target_time = get_seconds_until_next_target(args.morning_start, 0)
                    msg = (f"[QUOTA GUARD] Đã bảo toàn thành công {args.reserve} requests cho sáng mai!\n"
                           f"    + Hệ thống tự động chuyển sang chế độ ngủ bảo toàn quota.\n"
                           f"    + Thời điểm thức dậy: {target_time.strftime('%H:%M:%S %d/%m/%Y')} (đúng 06:00 AM)")

                sleep_countdown(secs_to_wait, msg)

    except KeyboardInterrupt:
        print("\n\n[*] Người dùng chủ động dừng tiến trình crawler.")
        rotator.print_summary()
    finally:
        set_windows_keep_awake(False)
        print("[*] Đã khôi phục cài đặt nguồn điện máy tính về mặc định.")

if __name__ == "__main__":
    main()
