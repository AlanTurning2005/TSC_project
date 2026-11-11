r"""
inspect_best_trial.py
=============================================================================
CÔNG CỤ KIỂM TRA CHI TIẾT KẾT QUẢ HIỆU CHUẨN TỐT NHẤT (BEST TRIAL INSPECTION)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
=============================================================================
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Cấu hình cache thư mục tạm cho Matplotlib
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

# Hỗ trợ UTF-8 console Windows
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "data" / "processed"
BEST_JSON = PROCESSED_DIR / "cmaes_best_params.json"
HISTORY_CSV = PROCESSED_DIR / "cmaes_trial_history.csv"
OUTPUT_PNG = PROCESSED_DIR / "best_trial_inspection.png"

def main():
    if not BEST_JSON.exists():
        print(f"[!] Không tìm thấy: {BEST_JSON}")
        return
    if not HISTORY_CSV.exists():
        print(f"[!] Không tìm thấy: {HISTORY_CSV}")
        return

    with open(BEST_JSON, "r", encoding="utf-8") as f:
        best_data = json.load(f)

    df_hist = pd.read_csv(HISTORY_CSV)

    best_val = best_data["best_value"]
    best_lambda = np.array(best_data["best_lambda_vps"])
    best_attrs = best_data["best_user_attrs"]
    total_trials = len(df_hist)

    print("=" * 70)
    print("      BÁO CÁO CHI TIẾT NGHIỆM TỐI ƯU HIỆU CHUẨN (CMA-ES)")
    print("=" * 70)
    print(f"[*] Ngày kiểm chuẩn (Target Date): {best_data.get('target_date', 'N/A')}")
    print(f"[*] Tổng số vòng thử nghiệm     : {total_trials} trials")
    best_row = df_hist.loc[df_hist["value"].idxmin()]
    print(f"[*] Trial tốt nhất               : Trial #{int(best_row['number'])}")
    print(f"[*] Điểm hàm mục tiêu (Loss)     : {best_val:.4f} (Khởi điểm Trial 0: {df_hist['value'].iloc[0]:.4f})")
    print(f"    - Sai số vận tốc RMSE_w     : {best_attrs['rmse_w']:.3f} km/h")
    print(f"    - Phạt độ trơn (Smooth)     : {best_attrs['smooth_term']:.4f}")
    print(f"    - Phạt tiên nghiệm (Prior)  : {best_attrs['prior_term']:.4f}")
    print(f"    - Phạt dung lượng (BPR)     : {best_attrs['bpr_penalty']:.4f}")
    print("-" * 70)
    print("[*] SỨC KHỎE MÔ PHỎNG VI MÔ (SIMULATION HEALTH):")
    print(f"    - Tỷ lệ hoàn thành hành trình (TCR) : {best_attrs['tcr']*100:.2f}% (Ngưỡng đạt: >= 90%)")
    print(f"    - Tỷ lệ xe kẹt giải cứu (Teleport) : {best_attrs['teleport_rate']*100:.3f}% (Ngưỡng đạt: < 0.1%)")
    print(f"    - Tỷ lệ nạp xe thành công (ICR)    : {best_attrs['icr']*100:.2f}% (Ngưỡng đạt: >= 98%)")
    print(f"    - Tắc nghẽn cửa ngõ biên (GBR)      : {best_attrs['gbr']*100:.2f}%")
    print(f"    - Tổng xe nạp vào mạng lưới        : {int(best_attrs['total_inserted']):,} xe")
    print(f"    - Tổng xe hoàn thành hành trình    : {int(best_attrs['total_arrived']):,} xe")
    print("=" * 70)

    # In phân rã vector nhu cầu
    time_slices = ["06:30-07:00", "07:00-07:30", "07:30-08:00", "08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"]
    prior_lambda = [0.85, 1.25, 1.50, 1.35, 1.10, 0.90, 0.85]

    print("\n" + "=" * 70)
    print("      PHÂN RÃ VECTOR NHU CẦU THEO KHUNG GIỜ (LAMBDA)")
    print("=" * 70)
    print(f"{'Khung giờ':<15} | {'Tiên nghiệm (Prior)':<20} | {'Hiệu chuẩn (Lambda*)':<20} | {'Độ lệch (%)':<12}")
    print("-" * 70)
    for ts, pr, cl in zip(time_slices, prior_lambda, best_lambda):
        diff_pct = ((cl - pr) / pr) * 100.0
        sign = "+" if diff_pct > 0 else ""
        print(f"{ts:<15} | {pr:<20.4f} | {cl:<20.4f} | {sign}{diff_pct:.1f}%")
    print("=" * 70)

    # In top 5 trials tốt nhất để kiểm tra tính ổn định
    print("\n" + "=" * 70)
    print("      TOP 5 TRIALS CÓ LOSS THẤP NHẤT (KIỂM TRA ĐỘ HỘI TỤ)")
    print("=" * 70)
    cols = ['number', 'value', 'user_attrs_rmse_w', 'user_attrs_smooth_term', 'user_attrs_prior_term', 'user_attrs_tcr', 'user_attrs_teleport_rate']
    top5 = df_hist.sort_values('value')[cols].head(5).copy()
    top5.columns = ['Trial', 'Loss', 'RMSE_w', 'Smooth', 'Prior', 'TCR', 'Teleport']
    print(top5.to_string(index=False))
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Vẽ Biểu đồ Chẩn đoán Đồ thị 2 Panel chuẩn Khoa học
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

    # Panel 1: So sánh Đường Nhu cầu: Prior vs Calibrated Lambda*
    x = np.arange(len(time_slices))

    ax1.plot(x, prior_lambda, marker='o', linestyle='--', color='#2b5c8f', linewidth=2, label='Tiên nghiệm (HOUTRANS Prior)')
    ax1.plot(x, best_lambda, marker='s', linestyle='-', color='#d95f02', linewidth=2.5, label='Nghiệm tối ưu CMA-ES (Lambda*)')
    
    # Fill dải chênh lệch
    ax1.fill_between(x, prior_lambda, best_lambda, color='#d95f02', alpha=0.15, label='Điều chỉnh thích ứng thực tế')

    ax1.set_title("So sánh Đường Nhu cầu: Tiên nghiệm vs Hiệu chuẩn", fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel("Khung giờ Cao điểm Sáng", fontsize=11)
    ax1.set_ylabel("Hệ số nhu cầu Lambda (xe/giây)", fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(time_slices, rotation=25, ha='right', fontsize=9)
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.legend(loc='upper left', frameon=True)

    # Panel 2: Độ Ổn định của Top 10 Trials
    top10 = df_hist.sort_values('value').head(10)
    lambda_cols = [c for c in df_hist.columns if c.startswith('params_lambda')]
    
    for idx, row in top10.iterrows():
        l_vals = [row[c] for c in lambda_cols]
        alpha = 0.9 if row['number'] == best_row['number'] else 0.35
        color = '#d95f02' if row['number'] == best_row['number'] else '#7570b3'
        lw = 2.5 if row['number'] == best_row['number'] else 1.2
        lbl = f"Best (Trial #{int(best_row['number'])})" if row['number'] == best_row['number'] else None
        ax2.plot(x, l_vals, marker='.', linestyle='-', color=color, alpha=alpha, linewidth=lw, label=lbl)

    ax2.set_title("Tính Ổn định của Nghiệm: Phân bố Tham số Top 10 Trials", fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel("Khung giờ Cao điểm Sáng", fontsize=11)
    ax2.set_ylabel("Hệ số nhu cầu Lambda (xe/giây)", fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels(time_slices, rotation=25, ha='right', fontsize=9)
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.legend(loc='upper left', frameon=True)

    plt.tight_layout()
    fig.savefig(OUTPUT_PNG, dpi=300)
    plt.close(fig)
    print(f"\n[+] Đã xuất biểu đồ chẩn đoán tại: {OUTPUT_PNG.resolve()}")

if __name__ == "__main__":
    main()
