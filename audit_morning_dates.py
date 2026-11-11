import sys
import pandas as pd
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

data_dir = Path("macro_traffic_crawler/data/processed")

records = []
for f in ["macro_traffic_history.csv", "macro_traffic_dense_1min.csv", "data_hcmc_20_10.csv", "hcmc_19_10_data.csv"]:
    p = data_dir / f
    if not p.exists():
        continue
    df = pd.read_csv(p, low_memory=False)
    for col in ["date", "time", "point_id", "confidence", "current_speed_kmh"]:
        if col not in df.columns:
            continue
    df["source_file"] = f
    records.append(df[["date", "time", "point_id", "confidence", "current_speed_kmh", "source_file"]])

combined = pd.concat(records, ignore_index=True).drop_duplicates(subset=["date", "time", "point_id"])
combined["hour"] = pd.to_numeric(combined["time"].str.slice(0, 2), errors="coerce")

print("=== TỔNG HỢP CÁC NGÀY VÀ KHUNG GIỜ BUỔI SÁNG (07:00 - 09:00) ===")
summary = []
for d, g in combined.groupby("date"):
    m_sub = g[(g["hour"] >= 7) & (g["hour"] < 9)]
    d_obj = pd.to_datetime(d)
    day_name = d_obj.strftime("%A")
    is_weekday = d_obj.weekday() < 5
    
    total_points = g["point_id"].nunique()
    morning_slices = m_sub["time"].nunique()
    morning_records = len(m_sub)
    morning_conf = m_sub["confidence"].mean() if not m_sub.empty else 0.0
    morning_speed = m_sub["current_speed_kmh"].mean() if not m_sub.empty else 0.0
    
    summary.append({
        "date": d,
        "day": day_name,
        "is_weekday": is_weekday,
        "total_day_records": len(g),
        "day_time_min": g["time"].min(),
        "day_time_max": g["time"].max(),
        "morning_slices (07-09h)": morning_slices,
        "morning_records": morning_records,
        "morning_mean_conf": round(morning_conf, 3),
        "morning_mean_speed": round(morning_speed, 2),
        "has_full_morning": morning_slices >= 8  # ít nhất 8 lát cắt 15p hoặc nhiều lát 1-5p
    })

sum_df = pd.DataFrame(summary).sort_values("date")
print(sum_df.to_string(index=False))
