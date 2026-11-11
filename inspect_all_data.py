import sys
import pandas as pd
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

data_dir = Path("macro_traffic_crawler/data")
print("=== CHECKING ALL PROCESSED DATASETS ===")

all_dfs = []
for f in sorted((data_dir / "processed").glob("*.csv")):
    if "optuna" in f.name or "cmaes" in f.name:
        continue
    try:
        df = pd.read_csv(f, low_memory=False)
        print(f"\nFile: {f.name} (Total rows: {len(df):,})")
        if "timestamp" in df.columns:
            df["dt"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Ho_Chi_Minh")
            dates = df["dt"].dt.date.value_counts().sort_index()
            for d, c in dates.items():
                sub = df[df["dt"].dt.date == d]
                h_min = sub["dt"].dt.time.min()
                h_max = sub["dt"].dt.time.max()
                conf_mean = sub["confidence"].mean() if "confidence" in sub.columns else None
                conf_min = sub["confidence"].min() if "confidence" in sub.columns else None
                conf_gt90 = (sub["confidence"] >= 0.90).mean() * 100 if "confidence" in sub.columns else None
                print(f"   • Ngày {d} ({d.strftime('%A')}): {c:,} dòng | Từ {h_min} đến {h_max} | Conf TB: {conf_mean:.3f} (>=0.90: {conf_gt90:.1f}%)")
                all_dfs.append({
                    "file": f.name,
                    "date": str(d),
                    "day_name": d.strftime("%A"),
                    "rows": c,
                    "time_start": str(h_min),
                    "time_end": str(h_max),
                    "conf_mean": conf_mean,
                    "points": sub["point_id"].nunique() if "point_id" in sub.columns else 0
                })
    except Exception as e:
        print(f"   [!] Error {f.name}: {e}")

summary_df = pd.DataFrame(all_dfs)
print("\n=== TỔNG HỢP CÁC NGÀY ĐÃ THU THẬP ===")
if not summary_df.empty:
    print(summary_df.to_string(index=False))

