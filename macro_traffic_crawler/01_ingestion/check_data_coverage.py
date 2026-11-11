import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

files = [
    'macro_traffic_crawler/data/processed/macro_traffic_history.csv',
    'macro_traffic_crawler/data/processed/macro_traffic_dense_1min.csv',
    'macro_traffic_crawler/data/processed/data_hcmc_20_10.csv',
    'macro_traffic_crawler/data/processed/hcmc_19_10_data.csv'
]

dfs = []
for f in files:
    p = Path(f)
    if p.exists():
        df = pd.read_csv(p, usecols=['timestamp', 'point_id'])
        df['source_file'] = p.name
        dfs.append(df)

all_df = pd.concat(dfs, ignore_index=True)

# Parse timestamps with ISO8601 and convert to Asia/Ho_Chi_Minh (UTC+7)
all_df['dt'] = pd.to_datetime(all_df['timestamp'], format='ISO8601', utc=True)
all_df['dt_vn'] = all_df['dt'].dt.tz_convert('Asia/Ho_Chi_Minh')
all_df = all_df.dropna(subset=['dt_vn'])

all_df['dt_sec'] = all_df['dt_vn'].dt.floor('s')
unique_df = all_df.drop_duplicates(subset=['dt_sec', 'point_id'])

# Group by unique snapshot timestamp
snapshots = unique_df.groupby('dt_sec').size().reset_index(name='point_count')
snapshots['date'] = snapshots['dt_sec'].dt.date
snapshots['time'] = snapshots['dt_sec'].dt.time
snapshots['hour'] = snapshots['dt_sec'].dt.hour
snapshots['weekday'] = snapshots['dt_sec'].dt.day_name()
snapshots['day_of_week'] = snapshots['dt_sec'].dt.weekday

vn_days = {
    'Monday': 'Thứ Hai',
    'Tuesday': 'Thứ Ba',
    'Wednesday': 'Thứ Tư',
    'Thursday': 'Thứ Năm',
    'Friday': 'Thứ Sáu',
    'Saturday': 'Thứ Bảy',
    'Sunday': 'Chủ Nhật'
}

dates = sorted(snapshots['date'].unique())

print("=" * 105)
print("BÁO CÁO TOÀN DIỆN VỀ ĐỘ PHỦ DỮ LIỆU CÀO GIAO THÔNG (16:00 - 21:00 & CÁC NGÀY TRONG TUẦN)")
print("=" * 105)

results = []

for d in dates:
    sub = snapshots[snapshots['date'] == d].sort_values('dt_sec')
    wname = sub['weekday'].iloc[0]
    vn_day = vn_days.get(wname, wname)
    dow = sub['day_of_week'].iloc[0]
    
    t_min = sub['dt_sec'].min()
    t_max = sub['dt_sec'].max()
    dur_hours = (t_max - t_min).total_seconds() / 3600.0
    
    if len(sub) > 1:
        diffs = sub['dt_sec'].diff().dropna().dt.total_seconds()
        median_int = diffs.median()
    else:
        median_int = 0
        
    # Lọc riêng khung giờ 16:00 đến 21:00 (4h chiều đến 9h tối)
    sub_pm = sub[(sub['dt_sec'].dt.hour >= 16) & (sub['dt_sec'].dt.hour <= 21)]
    
    has_pm = len(sub_pm) > 0
    if len(sub_pm) > 1:
        pm_t_min = sub_pm['dt_sec'].min()
        pm_t_max = sub_pm['dt_sec'].max()
        pm_start_str = pm_t_min.strftime('%H:%M')
        pm_end_str = pm_t_max.strftime('%H:%M')
        pm_count = len(sub_pm)
        pm_dur_h = (pm_t_max - pm_t_min).total_seconds() / 3600.0
        pm_diffs = sub_pm['dt_sec'].diff().dropna().dt.total_seconds()
        pm_med_int = pm_diffs.median()
        
        # Đánh giá: 16h - 21h (khoảng 4-5 tiếng), interval ~60s - 120s
        # Chu kỳ cào interval 60s trên thực tế mỗi vòng mất 66 điểm * 0.2s + 60s = ~75s - 120s
        is_dense_1to2min = (pm_med_int <= 150)
        is_full_5h = (pm_t_min.hour <= 16 and pm_t_min.minute <= 15 and (pm_t_max.hour >= 20 and pm_t_max.minute >= 45 or pm_t_max.hour >= 21))
        
        if is_dense_1to2min and is_full_5h:
            status = "ĐỦ TRỌN VẸN (16h-21h, ~1-2p)"
        elif is_dense_1to2min and pm_dur_h >= 3.0:
            status = f"GẦN ĐỦ ({pm_dur_h:.1f}h, ~1-2p)"
        elif is_dense_1to2min:
            status = f"THIẾU GIỜ ({pm_dur_h:.1f}h, ~1-2p)"
        else:
            status = f"CHƯA ĐẠT (Interval {pm_med_int/60:.1f}p)"
    else:
        pm_start_str = "N/A"
        pm_end_str = "N/A"
        pm_count = len(sub_pm)
        pm_dur_h = 0.0
        pm_med_int = 0
        status = "KHÔNG CÓ DỮ LIỆU"

    results.append({
        'date': d,
        'dow': dow,
        'vn_day': vn_day,
        'total_snaps': len(sub),
        'day_span': f"{t_min.strftime('%H:%M')} -> {t_max.strftime('%H:%M')}",
        'pm_span': f"{pm_start_str} -> {pm_end_str}",
        'pm_snaps': pm_count,
        'pm_dur_h': pm_dur_h,
        'pm_med_int': pm_med_int,
        'status': status
    })

    print(f"Ngày: {d} | {vn_day:<10} | Tổng ngày: {t_min.strftime('%H:%M')} -> {t_max.strftime('%H:%M')} ({len(sub):>3} snaps)")
    print(f"   => Khung 16h-21h: {pm_start_str} -> {pm_end_str} | Snaps: {pm_count:>3} | Độ dài: {pm_dur_h:>4.2f}h | Interval: {pm_med_int:>3.0f}s (~{pm_med_int/60:.1f}p) | [{status}]")
    print("-" * 105)

# Bảng tổng hợp theo 7 ngày trong tuần
print("\n" + "=" * 105)
print("ĐÁNH GIÁ TỔNG QUAN THEO 7 THỨ TRONG TUẦN (MỤC TIÊU: 16:00 - 21:00, INTERVAL ~1-2 PHÚT):")
print("=" * 105)
all_weekdays = [
    (0, 'Thứ Hai'),
    (1, 'Thứ Ba'),
    (2, 'Thứ Tư'),
    (3, 'Thứ Năm'),
    (4, 'Thứ Sáu'),
    (5, 'Thứ Bảy'),
    (6, 'Chủ Nhật')
]

for dow, name in all_weekdays:
    matching = [r for r in results if r['dow'] == dow]
    if not matching:
        print(f"❌ {name:<10}: HOÀN TOÀN CHƯA CÓ DỮ LIỆU NÀO!")
    else:
        full_days = [r for r in matching if "ĐỦ TRỌN VẸN" in r['status']]
        near_days = [r for r in matching if "GẦN ĐỦ" in r['status']]
        
        detail_strs = [f"{r['date']} ({r['status']}, {r['pm_span']}, {r['pm_snaps']} snaps)" for r in matching]
        
        if full_days:
            best_str = "; ".join([f"{r['date']} ({r['pm_span']}, {r['pm_snaps']} snaps)" for r in full_days])
            print(f"✅ {name:<10}: ĐÃ ĐỦ TRỌN VẸN KHUNG 16H-21H -> {best_str}")
        elif near_days:
            print(f"⚠️ {name:<10}: CÓ DỮ LIỆU GẦN ĐỦ (cần cào bổ sung) -> {'; '.join(detail_strs)}")
        else:
            print(f"❌ {name:<10}: CHƯA ĐẠT (Thiếu khung 16h-21h hoặc interval quá thưa) -> {'; '.join(detail_strs)}")

print("=" * 105)
