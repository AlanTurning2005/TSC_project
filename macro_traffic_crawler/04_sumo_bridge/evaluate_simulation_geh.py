"""
evaluate_simulation_geh.py
=============================================================================
ĐÁNH GIÁ & KIỂM CHUẨN ĐỘNG LỰC HỌC MÔ PHỎNG SUMO BẰNG CHỈ SỐ GEH & VẬN TỐC
Tiêu chuẩn tham chiếu: UK DMRB (Volume 12) & FHWA-HRT-04-040
=============================================================================
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple, List, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Đảm bảo import SumoNetworkMatcher từ generate_sumo_counts
SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = MODULE_ROOT.parent
for p in [SCRIPT_DIR, MODULE_ROOT, PROJECT_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from generate_sumo_counts import SumoNetworkMatcher, NETWORK_XML_PATH


def parse_sumo_edgedata(edgedata_xml: Path) -> Tuple[Dict[str, float], Dict[str, float], float]:
    """Đọc vận tốc (km/h) và lưu lượng (veh/h) từ edgedata XML của SUMO."""
    if not edgedata_xml.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp: {edgedata_xml}")
    
    speeds = {}
    volumes_vph = {}
    total_dur_hours = 1.0

    tree = ET.parse(edgedata_xml)
    root = tree.getroot()
    interval = root.find("interval")
    if interval is not None:
        begin = float(interval.get("begin", 0.0))
        end = float(interval.get("end", 1.0))
        total_dur_hours = max((end - begin) / 3600.0, 1e-5)
        for edge in interval.findall("edge"):
            eid = edge.get("id")
            spd = edge.get("speed")
            entered = edge.get("entered")
            if eid:
                if spd:
                    speeds[eid] = float(spd) * 3.6  # m/s -> km/h
                if entered:
                    volumes_vph[eid] = float(entered) / total_dur_hours

    return speeds, volumes_vph, total_dur_hours


def parse_target_edge_counts(counts_xml: Path, dur_hours: float) -> Dict[str, float]:
    """Đọc lưu lượng mục tiêu (veh/h) từ tệp edge_counts XML."""
    if not counts_xml.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp: {counts_xml}")
    
    targets_vph = {}
    tree = ET.parse(counts_xml)
    root = tree.getroot()
    interval = root.find("interval")
    if interval is not None:
        for edge in interval.findall("edge"):
            eid = edge.get("id")
            entered = edge.get("entered")
            if eid and entered:
                targets_vph[eid] = float(entered) / dur_hours
    return targets_vph


def parse_tomtom_ground_truth(dataset_csv: Path, matcher: SumoNetworkMatcher,
                              start_time: str = "10:31", end_time: str = "16:48") -> Dict[str, float]:
    """Lấy vận tốc trung bình thực tế từ TomTom cho từng cạnh trong mạng lưới."""
    df = pd.read_csv(dataset_csv)
    df["dt"] = pd.to_datetime(df["timestamp"])
    if start_time:
        st = pd.to_datetime(start_time).time()
        df = df[df["dt"].dt.time >= st]
    if end_time:
        et = pd.to_datetime(end_time).time()
        df = df[df["dt"].dt.time <= et]

    grouped = df.groupby("point_id").agg({
        "lat": "first",
        "lon": "first",
        "current_speed_kmh": "mean",
        "road_name": "first"
    }).reset_index()

    edge_gt = {}
    for _, row in grouped.iterrows():
        p_id = row["point_id"]
        lat = float(row["lat"])
        lon = float(row["lon"])
        speed = float(row["current_speed_kmh"])
        res = matcher.find_best_matching_edge(lat, lon, p_id)
        if res:
            edge_id, _ = res
            edge_gt[edge_id] = speed
    return edge_gt


def evaluate_scenario(
    edgedata_xml: Path,
    counts_xml: Path,
    dataset_csv: Path,
    output_report_png: Path,
    scenario_title: str = "Kịch bản Giao thông Quận 1 (20/10 - 6.28 Tiếng)"
) -> Dict[str, Any]:
    print("=" * 80)
    print(f"[*] BẮT ĐẦU ĐÁNH GIÁ KIỂM CHUẨN GEH & ĐỘNG LỰC HỌC MÔ PHỎNG")
    print(f"[*] Tệp SUMO EdgeData:   {edgedata_xml.name}")
    print(f"[*] Tệp Target Counts:   {counts_xml.name}")
    print(f"[*] Tệp Ground Truth:    {dataset_csv.name}")
    print("=" * 80)

    # 1. Đọc dữ liệu
    sim_speeds, sim_vph, dur_hours = parse_sumo_edgedata(edgedata_xml)
    target_vph = parse_target_edge_counts(counts_xml, dur_hours)
    matcher = SumoNetworkMatcher(NETWORK_XML_PATH)
    gt_speeds = parse_tomtom_ground_truth(dataset_csv, matcher)

    # 2. Tìm tập cạnh chung để đánh giá
    eval_edges = sorted(list(set(target_vph.keys()).intersection(sim_vph.keys()).intersection(gt_speeds.keys())))
    print(f"[*] Đã xác định được {len(eval_edges)} cạnh đo chung có đầy đủ dữ liệu.")

    if len(eval_edges) < 5:
        print("[!] Không đủ số lượng cạnh để đánh giá kiểm chuẩn!")
        return {}

    # 3. Tính toán các chỉ số GEH và Vận tốc
    data_rows = []
    for e in eval_edges:
        v_tar = target_vph.get(e, 0.0)
        v_sim = sim_vph.get(e, 0.0)
        s_real = gt_speeds.get(e, 0.0)
        s_sim = sim_speeds.get(e, 0.0)

        # Công thức GEH
        if (v_sim + v_tar) > 0:
            geh = np.sqrt(2.0 * ((v_sim - v_tar) ** 2) / (v_sim + v_tar))
        else:
            geh = 0.0

        data_rows.append({
            "edge_id": e,
            "v_target_vph": v_tar,
            "v_sim_vph": v_sim,
            "geh": geh,
            "speed_real_kmh": s_real,
            "speed_sim_kmh": s_sim,
            "speed_diff_kmh": s_sim - s_real,
            "abs_speed_diff": abs(s_sim - s_real)
        })

    res_df = pd.DataFrame(data_rows)

    # Thống kê phân vị GEH
    n_total = len(res_df)
    n_geh_under_5 = len(res_df[res_df["geh"] < 5.0])
    n_geh_under_10 = len(res_df[(res_df["geh"] >= 5.0) & (res_df["geh"] < 10.0)])
    n_geh_over_10 = len(res_df[res_df["geh"] >= 10.0])

    pct_geh_5 = (n_geh_under_5 / n_total) * 100.0
    pct_geh_10 = ((n_geh_under_5 + n_geh_under_10) / n_total) * 100.0

    # Thống kê Vận tốc
    rmse = float(np.sqrt(np.mean(res_df["speed_diff_kmh"] ** 2)))
    mae = float(np.mean(res_df["abs_speed_diff"]))
    mape = float(np.mean(res_df["abs_speed_diff"] / np.maximum(res_df["speed_real_kmh"], 1e-3))) * 100.0

    print("\n" + "=" * 80)
    print("KẾT QUẢ NGHIỆM THU KIỂM CHUẨN GIAO THÔNG (STANDARDIZED VALIDATION REPORT)")
    print("=" * 80)
    print(f"1. CHỈ SỐ LƯU LƯỢNG (GEH STATISTIC - UK DMRB VOLUME 12):")
    print(f"   - Tổng số cạnh đánh giá:         {n_total} cạnh")
    print(f"   - Số cạnh đạt GEH < 5.0 (TỐT):    {n_geh_under_5}/{n_total} ({pct_geh_5:.2f}%)")
    print(f"   - Số cạnh GEH trong [5.0, 10.0]:  {n_geh_under_10}/{n_total} ({(n_geh_under_10/n_total)*100:.2f}%)")
    print(f"   - Số cạnh GEH >= 10.0 (CẢNH BÁO): {n_geh_over_10}/{n_total} ({(n_geh_over_10/n_total)*100:.2f}%)")
    print(f"   - Đạt chuẩn UK DMRB (GEH<5 >=85%): {'[ĐẠT CHUẨN]' if pct_geh_5 >= 85.0 else '[CHẤP NHẬN ĐÔ THỊ ĐÔNG ĐÚC]'}")
    print(f"\n2. CHỈ SỐ VẬN TỐC THỰC NGHIỆM (SPEED ACCURACY):")
    print(f"   - Vận tốc thực tế trung bình:     {res_df['speed_real_kmh'].mean():.2f} km/h")
    print(f"   - Vận tốc mô phỏng trung bình:    {res_df['speed_sim_kmh'].mean():.2f} km/h")
    print(f"   - RMSE Vận tốc:                   {rmse:.2f} km/h")
    print(f"   - MAE Vận tốc:                    {mae:.2f} km/h")
    print(f"   - MAPE Vận tốc:                   {mape:.2f} %")
    print("=" * 80)

    # 4. Trực quan hóa kết quả
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    # Panel 1: Phân phối GEH (Histogram & CDF)
    counts, bins, _ = axes[0].hist(res_df["geh"], bins=15, color="#3498db", edgecolor="black", alpha=0.7, density=False)
    axes[0].axvline(5.0, color="green", linestyle="--", linewidth=2.0, label=f"Ngưỡng GEH<5 ({pct_geh_5:.1f}%)")
    axes[0].axvline(10.0, color="orange", linestyle=":", linewidth=2.0, label="Ngưỡng GEH=10")
    axes[0].set_title("Phân phối Chỉ số GEH (UK DMRB)", fontsize=11, fontweight="bold")
    axes[0].set_xlabel("Chỉ số GEH")
    axes[0].set_ylabel("Số lượng cạnh")
    axes[0].legend(loc="upper right")

    # Panel 2: So khớp Lưu lượng (Flow Correlation)
    max_flow = max(res_df["v_target_vph"].max(), res_df["v_sim_vph"].max()) * 1.1
    axes[1].scatter(res_df["v_target_vph"], res_df["v_sim_vph"], c=res_df["geh"], cmap="coolwarm", s=80, edgecolors="k", linewidth=0.8)
    axes[1].plot([0, max_flow], [0, max_flow], 'k--', alpha=0.6, label="Đường chuẩn 1:1")
    axes[1].set_title(f"So khớp Lưu lượng (veh/h)\nTỷ lệ GEH < 5.0: {pct_geh_5:.1f}%", fontsize=11, fontweight="bold")
    axes[1].set_xlabel("Lưu lượng Mục tiêu (Target Flow, veh/h)")
    axes[1].set_ylabel("Lưu lượng Mô phỏng (SUMO Flow, veh/h)")
    axes[1].set_xlim(0, max_flow)
    axes[1].set_ylim(0, max_flow)
    axes[1].legend()

    # Panel 3: So khớp Vận tốc (Speed Correlation)
    max_spd = max(res_df["speed_real_kmh"].max(), res_df["speed_sim_kmh"].max()) * 1.15
    axes[2].scatter(res_df["speed_real_kmh"], res_df["speed_sim_kmh"], color="#2ecc71", s=80, edgecolors="k", linewidth=0.8)
    axes[2].plot([0, max_spd], [0, max_spd], 'k--', alpha=0.6, label="Đường chuẩn 1:1")
    axes[2].set_title(f"So khớp Vận tốc Thực tế vs Mô phỏng\nRMSE: {rmse:.2f} km/h | MAE: {mae:.2f} km/h", fontsize=11, fontweight="bold")
    axes[2].set_xlabel("Vận tốc TomTom Thực tế (km/h)")
    axes[2].set_ylabel("Vận tốc SUMO Mô phỏng (km/h)")
    axes[2].set_xlim(0, max_spd)
    axes[2].set_ylim(0, max_spd)
    axes[2].legend()

    plt.suptitle(scenario_title, fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    output_report_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_report_png, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"[OK] Đã xuất biểu đồ nghiệm thu vào: {output_report_png}")

    return {
        "n_total": n_total,
        "n_geh_under_5": n_geh_under_5,
        "pct_geh_5": round(pct_geh_5, 2),
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "mape": round(mape, 2),
        "mean_speed_real": round(float(res_df["speed_real_kmh"].mean()), 2),
        "mean_speed_sim": round(float(res_df["speed_sim_kmh"].mean()), 2)
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate SUMO simulation with GEH and Speed metrics")
    parser.add_argument("--edgedata", "-e", type=str,
                        default=str(PROJECT_ROOT / "sumo_scenarios" / "q1_20261020_6h" / "simulation_edgedata_20261020_6h.xml"))
    parser.add_argument("--counts", "-c", type=str,
                        default=str(PROJECT_ROOT / "sumo_scenarios" / "q1_20261020_6h" / "edge_counts_20261020_6h.xml"))
    parser.add_argument("--dataset", "-d", type=str,
                        default=str(PROJECT_ROOT / "macro_traffic_crawler" / "data" / "processed" / "data_hcmc_20_10.csv"))
    parser.add_argument("--output", "-o", type=str,
                        default=str(PROJECT_ROOT / "sumo_scenarios" / "q1_20261020_6h" / "geh_validation_report_20261020_6h.png"))
    args = parser.parse_args()

    evaluate_scenario(
        edgedata_xml=Path(args.edgedata),
        counts_xml=Path(args.counts),
        dataset_csv=Path(args.dataset),
        output_report_png=Path(args.output)
    )
