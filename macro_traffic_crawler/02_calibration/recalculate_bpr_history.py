"""
recalculate_bpr_history.py
==========================
Tiện ích cập nhật lại lưu lượng ước tính (est_volume_vph) và tốc độ xe đến (arrival_rate_vps)
trên các file CSV đã cào bằng hàm BPR hiệu chuẩn cho TP.HCM (alpha = 0.35, beta = 2.5).

Giúp bạn KHÔNG CẦN CÀO LẠI DỮ LIỆU: Toàn bộ thông số thô từ TomTom (current_travel_time,
free_flow_travel_time) sẽ được tính toán lại ngay lập tức với độ chính xác cao.
"""

import sys
import os
import pandas as pd
from pathlib import Path

# Hỗ trợ UTF-8 cho Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo import config và run_crawler từ 01_ingestion
_SCRIPT_DIR = Path(__file__).resolve().parent
_MODULE_ROOT = _SCRIPT_DIR.parent
_INGESTION_DIR = _MODULE_ROOT / "01_ingestion"
for p in [_SCRIPT_DIR, _MODULE_ROOT, _INGESTION_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from config import PROCESSED_DATA_DIR
from run_crawler import estimate_bpr_volume

ALPHA_HCM = 0.35
BETA_HCM = 2.5

def recalculate_file(csv_path: Path):
    if not csv_path.exists():
        print(f"[-] Khong tim thay file: {csv_path}")
        return

    print(f"\n[*] Dang xu ly: {csv_path.name}")
    df = pd.read_csv(csv_path)
    print(f"    + So dong du lieu: {len(df):,}")

    if "current_travel_time_s" not in df.columns or "free_flow_travel_time_s" not in df.columns:
        print("    [!] File thieu cot thoi gian hanh trinh TomTom. Bo qua.")
        return

    old_vol_mean = df["est_volume_vph"].mean() if "est_volume_vph" in df.columns else 0.0

    # Tinh toan lai theo BPR Viet Nam
    df["est_volume_vph"] = df.apply(
        lambda r: estimate_bpr_volume(
            float(r["current_travel_time_s"]),
            float(r["free_flow_travel_time_s"]),
            capacity=float(r.get("road_capacity_pcu", 1200.0)),
            alpha=ALPHA_HCM,
            beta=BETA_HCM
        ),
        axis=1
    )
    df["arrival_rate_vps"] = (df["est_volume_vph"] / 3600.0).round(4)

    new_vol_mean = df["est_volume_vph"].mean()

    # Ghi de lai file CSV voi du lieu da hieu chuan
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"    [+] Luu luong trung binh cu  (alpha=0.15, beta=4.0): {old_vol_mean:.1f} PCU/h")
    print(f"    [+] Luu luong trung binh moi (alpha=0.35, beta=2.5): {new_vol_mean:.1f} PCU/h")
    print(f"    [V] Cap nhat thanh cong vao: {csv_path}")

def main():
    print("="*60)
    print(f"[*] CAP NHAT BPR CHO DU LIEU DA CAO (ALPHA={ALPHA_HCM}, BETA={BETA_HCM})")
    print("="*60)

    files_to_update = [
        PROCESSED_DATA_DIR / "macro_traffic_history.csv",
        PROCESSED_DATA_DIR / "macro_traffic_dense_1min.csv"
    ]

    for p in files_to_update:
        if p.exists():
            recalculate_file(p)

    print("\n[V] HOAN TAT! Toan bo file CSV lich su da duoc hieu chuan theo chuan TP.HCM.")

if __name__ == "__main__":
    main()
