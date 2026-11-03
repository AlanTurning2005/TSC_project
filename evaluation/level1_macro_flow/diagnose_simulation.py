import sys
import os
import pandas as pd
import numpy as np

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đọc kết quả chi tiết đã xuất
df = pd.read_csv('evaluation/level1_macro_flow/reports/level1_edge_details.csv')
print("=== TỔNG QUAN 64 ĐIỂM ĐO ĐÃ KHỚP NGÀY 2026-10-20 ===")
print(f"V_obs:    mean = {df.v_obs_kmh.mean():.2f}, min = {df.v_obs_kmh.min():.2f}, max = {df.v_obs_kmh.max():.2f}")
print(f"V_sim:    mean = {df.v_sim_kmh.mean():.2f}, min = {df.v_sim_kmh.min():.2f}, max = {df.v_sim_kmh.max():.2f}")
print(f"V_free:   mean = {df.v_free_kmh.mean():.2f}, min = {df.v_free_kmh.min():.2f}, max = {df.v_free_kmh.max():.2f}")
print(f"V_median: mean = {df.v_median_kmh.mean():.2f}, min = {df.v_median_kmh.min():.2f}, max = {df.v_median_kmh.max():.2f}")

df['error'] = df['v_sim_kmh'] - df['v_obs_kmh']
df['abs_err'] = df['error'].abs()

print("\n=== PHÂN LOẠI CHIỀU LỆCH (BIAS DIRECTION) ===")
under_est = (df['error'] < -5).sum()
over_est = (df['error'] > 5).sum()
accurate = ((df['error'] >= -5) & (df['error'] <= 5)).sum()
print(f"Mô phỏng chạy QUÁ CHẬM so với thực tế (v_sim < v_obs - 5): {under_est}/{len(df)} điểm ({under_est/len(df)*100:.1f}%)")
print(f"Mô phỏng chạy QUÁ NHANH so với thực tế (v_sim > v_obs + 5): {over_est}/{len(df)} điểm ({over_est/len(df)*100:.1f}%)")
print(f"Mô phỏng CHẤP NHẬN ĐƯỢC (|sai số| <= 5 km/h):             {accurate}/{len(df)} điểm ({accurate/len(df)*100:.1f}%)")

print("\n=== TOP 15 TUYẾN ĐƯỜNG SAI SỐ LỚN NHẤT ===")
top15 = df.sort_values('abs_err', ascending=False).head(15)
for idx, r in top15.iterrows():
    print(f"{r['road_name']:<25} | Obs: {r['v_obs_kmh']:>5.1f} | Sim: {r['v_sim_kmh']:>5.1f} | Median: {r['v_median_kmh']:>5.1f} | Err: {r['error']:>6.1f} | LOS Obs: {r['los_obs']} | LOS Sim: {r['los_sim']}")

print("\n=== PHÂN BỐ SAI SỐ THEO HÀNH LANG (CORRIDOR GROUP) ===")
corridor_stats = df.groupby('road_name').agg(
    n_points=('point_id', 'count'),
    mean_obs=('v_obs_kmh', 'mean'),
    mean_sim=('v_sim_kmh', 'mean'),
    mean_err=('error', 'mean'),
    mae=('abs_err', 'mean')
).reset_index().sort_values('mae', ascending=False)
print(corridor_stats.head(10).to_string(index=False))
