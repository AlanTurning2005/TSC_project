"""
evaluate_level1_macro.py
=============================================================================
CẤP ĐỘ 1: KIỂM CHUẨN LƯU LƯỢNG & NHU CẦU VĨ MÔ (MACROSCOPIC FLOW CALIBRATION)
Tiêu chuẩn tham chiếu học thuật:
- UK DMRB Volume 12, Section 2 (Traffic Appraisal of Road Schemes)
- FHWA-HRT-04-040: Traffic Analysis Toolbox Vol III (Model Calibration)
- WisDOT (2014): Microsimulation Guidelines
- ODOT (2011): Protocol for Vissim/SUMO Simulation
=============================================================================
"""

import os
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple, List, Any, Optional

# Hỗ trợ Windows terminal utf-8 encoding chống lỗi UnicodeEncodeError
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
import matplotlib.pyplot as plt

# Định lập đường dẫn thư mục gốc dự án
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def parse_target_edge_counts(counts_xml_path: Path) -> Tuple[Dict[str, float], float]:
    """
    Đọc lưu lượng xe mục tiêu V_target từ tệp edge_counts.xml.
    Quy đổi số lượng xe thành lưu lượng theo giờ (veh/h).
    """
    if not counts_xml_path.exists():
        raise FileNotFoundError(f"[!] Không tìm thấy tệp đếm mục tiêu: {counts_xml_path}")

    target_vph: Dict[str, float] = {}
    duration_hours = 1.0

    tree = ET.parse(counts_xml_path)
    root = tree.getroot()
    interval = root.find("interval")
    if interval is not None:
        begin = float(interval.get("begin", 0.0))
        end = float(interval.get("end", 1.0))
        duration_hours = max((end - begin) / 3600.0, 1e-5)

        for edge in interval.findall("edge"):
            eid = edge.get("id")
            entered = edge.get("entered")
            if eid and entered:
                target_vph[eid] = float(entered) / duration_hours

    return target_vph, duration_hours


def parse_simulated_edgedata(edgedata_xml_path: Path) -> Tuple[Dict[str, float], Dict[str, float], float]:
    """
    Đọc lưu lượng xe mô phỏng V_SUMO (veh/h) và vận tốc trung bình (km/h) từ tệp simulation_edgedata.xml.
    """
    if not edgedata_xml_path.exists():
        raise FileNotFoundError(f"[!] Không tìm thấy tệp edgedata mô phỏng: {edgedata_xml_path}")

    sim_vph: Dict[str, float] = {}
    sim_speeds_kmh: Dict[str, float] = {}
    duration_hours = 1.0

    tree = ET.parse(edgedata_xml_path)
    root = tree.getroot()
    interval = root.find("interval")
    if interval is not None:
        begin = float(interval.get("begin", 0.0))
        end = float(interval.get("end", 1.0))
        duration_hours = max((end - begin) / 3600.0, 1e-5)

        for edge in interval.findall("edge"):
            eid = edge.get("id")
            entered = float(edge.get("entered", 0.0))
            departed = float(edge.get("departed", 0.0))
            speed = edge.get("speed")

            if eid:
                # Tổng xe đi qua = số xe từ cạnh trước vào + số xe xuất phát từ cạnh này
                sim_vph[eid] = (entered + departed) / duration_hours
                if speed is not None:
                    sim_speeds_kmh[eid] = float(speed) * 3.6  # m/s -> km/h

    return sim_vph, sim_speeds_kmh, duration_hours


def parse_simulation_summary(summary_xml_path: Optional[Path]) -> Dict[str, Any]:
    """
    Đọc thống kê nạp mạng vĩ mô từ tệp simulation_summary.xml của SUMO.
    Tính toán:
    - Insertion Completion Rate (ICR) = inserted / loaded
    - Gate Backlog Ratio (GBR) = waiting / loaded
    - Trip Completion Rate (TCR) = ended / inserted
    """
    if summary_xml_path is None or not summary_xml_path.exists():
        return {
            "status": "NOT_AVAILABLE",
            "message": "Chưa có tệp summary-output (cần bật thẻ <summary-output> trong .sumocfg)",
            "icr_percent": None,
            "gbr_percent": None,
            "tcr_percent": None,
            "teleported_vehicles": None
        }

    tree = ET.parse(summary_xml_path)
    root = tree.getroot()
    steps = root.findall("step")
    if not steps:
        return {"status": "EMPTY"}

    last_step = steps[-1]
    loaded = int(last_step.get("loaded", 0))
    inserted = int(last_step.get("inserted", 0))
    waiting = int(last_step.get("waiting", 0))
    ended = int(last_step.get("ended", 0))
    teleports = int(last_step.get("teleports", 0))

    icr = (inserted / max(loaded, 1)) * 100.0
    gbr = (waiting / max(loaded, 1)) * 100.0
    tcr = (ended / max(inserted, 1)) * 100.0

    return {
        "status": "AVAILABLE",
        "loaded_vehicles": loaded,
        "inserted_vehicles": inserted,
        "waiting_vehicles": waiting,
        "ended_vehicles": ended,
        "teleported_vehicles": teleports,
        "icr_percent": round(icr, 2),
        "gbr_percent": round(gbr, 2),
        "tcr_percent": round(tcr, 2),
        "is_icr_passed": icr >= 95.0,
        "is_gbr_passed": gbr < 5.0
    }


def compute_level1_metrics(
    target_vph: Dict[str, float],
    sim_vph: Dict[str, float]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Tính toán toàn bộ bộ chỉ số Cấp độ 1:
    1. Chỉ số GEH từng cạnh và phân loại phân vị (UK DMRB / FHWA).
    2. Hồi quy tuyến tính toàn mạng (R2, Slope s, Pearson correlation).
    """
    common_edges = sorted(list(set(target_vph.keys()).intersection(sim_vph.keys())))
    if not common_edges:
        raise ValueError("[!] Không tìm thấy cạnh chung nào giữa Target Counts và Simulated EdgeData!")

    data_rows = []
    for eid in common_edges:
        v_tar = target_vph[eid]
        v_sim = sim_vph[eid]

        # Công thức GEH Havers (1970)
        denom = v_sim + v_tar
        if denom > 0:
            geh = np.sqrt(2.0 * ((v_sim - v_tar) ** 2) / denom)
        else:
            geh = 0.0

        diff = v_sim - v_tar
        abs_diff = abs(diff)
        pct_err = (abs_diff / max(v_tar, 1e-3)) * 100.0

        if geh < 5.0:
            category = "TỐT (GEH < 5)"
        elif geh < 10.0:
            category = "CẢNH BÁO (5 <= GEH < 10)"
        else:
            category = "KHÔNG ĐẠT (GEH >= 10)"

        data_rows.append({
            "edge_id": eid,
            "v_target_vph": round(v_tar, 2),
            "v_sim_vph": round(v_sim, 2),
            "diff_vph": round(diff, 2),
            "abs_diff_vph": round(abs_diff, 2),
            "pct_error": round(pct_err, 2),
            "geh": round(geh, 2),
            "category": category
        })

    df = pd.DataFrame(data_rows)

    # 1. Thống kê phân vị GEH
    n_total = len(df)
    n_geh_under_5 = int((df["geh"] < 5.0).sum())
    n_geh_5_to_10 = int(((df["geh"] >= 5.0) & (df["geh"] < 10.0)).sum())
    n_geh_over_10 = int((df["geh"] >= 10.0).sum())

    pct_geh_under_5 = (n_geh_under_5 / n_total) * 100.0
    pct_geh_5_to_10 = (n_geh_5_to_10 / n_total) * 100.0
    pct_geh_over_10 = (n_geh_over_10 / n_total) * 100.0

    # 2. Hồi quy tuyến tính qua gốc tọa độ: V_sim = s * V_target
    v_tar_arr = df["v_target_vph"].to_numpy()
    v_sim_arr = df["v_sim_vph"].to_numpy()

    denom_slope = np.sum(v_tar_arr ** 2)
    slope = float(np.sum(v_tar_arr * v_sim_arr) / denom_slope) if denom_slope > 0 else 0.0

    # Hệ số xác định R2
    ss_res = np.sum((v_sim_arr - v_tar_arr) ** 2)
    ss_tot = np.sum((v_tar_arr - np.mean(v_tar_arr)) ** 2)
    r2 = float(1.0 - (ss_res / max(ss_tot, 1e-6)))

    # Hệ số tương quan Pearson
    corr = float(np.corrcoef(v_tar_arr, v_sim_arr)[0, 1]) if len(v_tar_arr) > 1 else 0.0

    metrics_summary = {
        "n_evaluated_edges": n_total,
        "n_geh_under_5": n_geh_under_5,
        "pct_geh_under_5": round(pct_geh_under_5, 2),
        "n_geh_5_to_10": n_geh_5_to_10,
        "pct_geh_5_to_10": round(pct_geh_5_to_10, 2),
        "n_geh_over_10": n_geh_over_10,
        "pct_geh_over_10": round(pct_geh_over_10, 2),
        "geh_mean": round(float(df["geh"].mean()), 2),
        "geh_max": round(float(df["geh"].max()), 2),
        "geh_median": round(float(df["geh"].median()), 2),
        "slope_s": round(slope, 3),
        "r2_score": round(r2, 3),
        "pearson_corr": round(corr, 3),
        # Đánh giá theo chuẩn quốc tế
        "fhwa_geh_passed": pct_geh_under_5 >= 85.0,
        "wisdot_r2_passed": r2 >= 0.85,
        "fhwa_slope_passed": 0.90 <= slope <= 1.10
    }

    return df, metrics_summary


def plot_level1_evaluation(
    df: pd.DataFrame,
    summary: Dict[str, Any],
    output_png: Path,
    title_suffix: str = "Quận 1, TP. Hồ Chí Minh"
) -> None:
    """
    Vẽ bộ 3 biểu đồ trực quan chuẩn mực theo phong cách học thuật (Publication-grade):
    1. Phân phối GEH (Histogram & ngưỡng DMRB 5.0, 10.0).
    2. Tương quan Lưu lượng (Scatter Plot & Đường chuẩn 1:1, Slope).
    3. Phân bố Sai lệch Lưu lượng (Residuals) để phát hiện cạnh nghẽn cổ chai.
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # -------------------------------------------------------------------------
    # Panel 1: Phân phối GEH
    # -------------------------------------------------------------------------
    counts, bins, patches = axes[0].hist(df["geh"], bins=15, edgecolor="black", alpha=0.75)
    for count, patch, b_left in zip(counts, patches, bins[:-1]):
        if b_left < 5.0:
            patch.set_facecolor("#2ecc71")  # Xanh: Tốt
        elif b_left < 10.0:
            patch.set_facecolor("#f39c12")  # Vàng: Cảnh báo
        else:
            patch.set_facecolor("#e74c3c")  # Đỏ: Nguy hiểm

    axes[0].axvline(5.0, color="#27ae60", linestyle="--", linewidth=2.0,
                    label=f"Ngưỡng GEH < 5.0: {summary['pct_geh_under_5']:.1f}%")
    axes[0].axvline(10.0, color="#c0392b", linestyle=":", linewidth=2.0,
                    label=f"Ngưỡng GEH = 10.0")
    axes[0].set_title("1. Phân phối Chỉ số GEH (UK DMRB Vol 12)", fontsize=11, fontweight="bold")
    axes[0].set_xlabel("Chỉ số Thống kê GEH")
    axes[0].set_ylabel("Số lượng Đoạn đường (Cạnh)")
    axes[0].legend(loc="upper right", frameon=True)

    # -------------------------------------------------------------------------
    # Panel 2: Tương quan Lưu lượng (Scatter & Regression)
    # -------------------------------------------------------------------------
    v_tar = df["v_target_vph"]
    v_sim = df["v_sim_vph"]
    max_val = max(v_tar.max(), v_sim.max()) * 1.1 if len(v_tar) > 0 else 1000

    scatter = axes[1].scatter(
        v_tar, v_sim,
        c=df["geh"], cmap="viridis",
        s=85, edgecolors="k", linewidth=0.8, alpha=0.85
    )
    cbar = plt.colorbar(scatter, ax=axes[1])
    cbar.set_label("Chỉ số GEH", fontsize=10)

    # Đường chuẩn 1:1 lý tưởng
    axes[1].plot([0, max_val], [0, max_val], "k--", alpha=0.6, label="Đường Chuẩn 1:1 (Lý tưởng)")

    # Đường hồi quy thực tế
    x_line = np.linspace(0, max_val, 100)
    axes[1].plot(x_line, summary["slope_s"] * x_line, "r-", linewidth=2.0,
                 label=f"Hồi quy: y = {summary['slope_s']:.2f}x (R² = {summary['r2_score']:.2f})")

    axes[1].set_title("2. Tương quan Lưu lượng (veh/h)", fontsize=11, fontweight="bold")
    axes[1].set_xlabel("Lưu lượng Mục tiêu (Target Flow, veh/h)")
    axes[1].set_ylabel("Lưu lượng Mô phỏng SUMO (veh/h)")
    axes[1].set_xlim(0, max_val)
    axes[1].set_ylim(0, max_val)
    axes[1].legend(loc="upper left", frameon=True)

    # -------------------------------------------------------------------------
    # Panel 3: Sai số Phân bổ (Residuals Plot)
    # -------------------------------------------------------------------------
    axes[2].scatter(df["v_target_vph"], df["diff_vph"], c="#34495e", s=60, edgecolors="k", alpha=0.7)
    axes[2].axhline(0.0, color="red", linestyle="--", linewidth=1.5, label="Sai số = 0 (Hoàn hảo)")
    axes[2].set_title("3. Biến thiên Sai lệch (V_sim - V_target)", fontsize=11, fontweight="bold")
    axes[2].set_xlabel("Lưu lượng Mục tiêu (Target Flow, veh/h)")
    axes[2].set_ylabel("Chênh lệch Lưu lượng (veh/h)")
    axes[2].legend(loc="upper right", frameon=True)

    plt.suptitle(f"BÁO CÁO NGHIỆM THU CẤP ĐỘ 1: LƯU LƯỢNG & NHU CẦU VĨ MÔ - {title_suffix}",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()

    output_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_png, dpi=200, bbox_inches="tight")
    plt.close()


def print_acceptance_table(summary: Dict[str, Any], summary_sim: Dict[str, Any]) -> None:
    """In bảng tổng kết nghiệm thu chuẩn học thuật ra Terminal."""
    print("=" * 85)
    print("           BẢNG NGHIỆM THU KIỂM CHUẨN CẤP ĐỘ 1 (ACCEPTANCE MATRIX)")
    print("=" * 85)
    print(f"{'Tiêu chí Đo lường':<30} | {'Thực nghiệm':<15} | {'Ngưỡng Tiêu chuẩn':<20} | {'Kết luận':<12}")
    print("-" * 85)

    # 1. GEH < 5.0
    status_geh = "[ĐẠT]" if summary["fhwa_geh_passed"] else "[CHƯA ĐẠT]"
    print(f"{'Tỷ lệ GEH < 5.0 (UK DMRB)':<30} | {summary['pct_geh_under_5']:>12.2f} % | {'>= 85.0 %':<20} | {status_geh:<12}")

    # 2. GEH 5 - 10
    print(f"{'Tỷ lệ GEH 5.0 - 10.0':<30} | {summary['pct_geh_5_to_10']:>12.2f} % | {'<= 15.0 %':<20} | {'[CHẤP NHẬN]':<12}")

    # 3. GEH >= 10
    status_geh10 = "[TỐT]" if summary["pct_geh_over_10"] < 5.0 else "[CẢNH BÁO]"
    print(f"{'Tỷ lệ GEH >= 10.0':<30} | {summary['pct_geh_over_10']:>12.2f} % | {'< 5.0 %':<20} | {status_geh10:<12}")

    # 4. R2 Score
    status_r2 = "[ĐẠT]" if summary["wisdot_r2_passed"] else "[CHƯA ĐẠT]"
    print(f"{'Hệ số Xác định R² (WisDOT)':<30} | {summary['r2_score']:>12.3f}   | {'>= 0.850':<20} | {status_r2:<12}")

    # 5. Slope s
    status_slope = "[ĐẠT]" if summary["fhwa_slope_passed"] else "[LỆCH QUY MÔ]"
    print(f"{'Độ dốc Hồi quy Slope (FHWA)':<30} | {summary['slope_s']:>12.3f}   | {'0.900 - 1.100':<20} | {status_slope:<12}")

    # 6. Tỷ lệ nạp mạng (nếu có)
    if summary_sim.get("status") == "AVAILABLE":
        icr = summary_sim.get("icr_percent", 0.0)
        status_icr = "[ĐẠT]" if summary_sim.get("is_icr_passed") else "[NGHẼN BIÊN]"
        print(f"{'Tỷ lệ Nạp mạng (ICR - ODOT)':<30} | {icr:>12.2f} % | {'>= 95.0 %':<20} | {status_icr:<12}")

        gbr = summary_sim.get("gbr_percent", 0.0)
        status_gbr = "[ĐẠT]" if summary_sim.get("is_gbr_passed") else "[CẢNH BÁO]"
        print(f"{'Tồn đọng Cửa ngõ (GBR)':<30} | {gbr:>12.2f} % | {'< 5.0 %':<20} | {status_gbr:<12}")
    else:
        print(f"{'Tỷ lệ Nạp mạng (ICR / GBR)':<30} | {'[CHƯA BẬT XML]':>15} | {'>= 95.0 %':<20} | {'[CHƯA ĐO]':<12}")

    print("=" * 85)


def run_evaluation_level1(
    counts_xml: Path,
    edgedata_xml: Path,
    summary_xml: Optional[Path],
    output_dir: Path,
    scenario_title: str = "Quận 1 (20/10)"
) -> Dict[str, Any]:
    """Hàm điều phối toàn bộ pipeline đánh giá Cấp độ 1."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_png = output_dir / "level1_macro_report.png"
    report_json = output_dir / "level1_metrics_summary.json"
    report_csv = output_dir / "level1_edge_details.csv"

    print("\n" + "=" * 85)
    print(f"[*] KHỞI CHẠY KIỂM ĐỊNH CẤP ĐỘ 1: LƯU LƯỢNG & NHU CẦU VĨ MÔ")
    print(f"[*] Tệp Đếm Mục Tiêu: {counts_xml}")
    print(f"[*] Tệp SUMO EdgeData: {edgedata_xml}")
    print("=" * 85)

    # 1. Đọc dữ liệu
    target_vph, dur_target = parse_target_edge_counts(counts_xml)
    sim_vph, sim_speeds, dur_sim = parse_simulated_edgedata(edgedata_xml)
    sim_summary = parse_simulation_summary(summary_xml)

    # 2. Tính toán
    df, metrics = compute_level1_metrics(target_vph, sim_vph)

    # 3. Xuất bảng nghiệm thu
    print_acceptance_table(metrics, sim_summary)

    # 4. Vẽ đồ thị và lưu kết quả
    plot_level1_evaluation(df, metrics, report_png, title_suffix=scenario_title)
    df.to_csv(report_csv, index=False, encoding="utf-8-sig")

    full_report = {
        "scenario": scenario_title,
        "metrics": metrics,
        "summary_simulation": sim_summary
    }
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=4, ensure_ascii=False)

    print(f"\n[OK] Đã xuất báo cáo đồ họa: {report_png}")
    print(f"[OK] Đã xuất số liệu JSON:    {report_json}")
    print(f"[OK] Đã xuất bảng chi tiết:   {report_csv}")
    print("=" * 85)

    return full_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate SUMO Simulation - Level 1 Macro Flow")
    parser.add_argument("--counts", "-c", type=str,
                        default=str(PROJECT_ROOT / "sumo_scenarios" / "q1_20261020_6h" / "edge_counts_20261020_6h.xml"),
                        help="Đường dẫn file edge_counts.xml")
    parser.add_argument("--edgedata", "-e", type=str,
                        default=str(PROJECT_ROOT / "sumo_scenarios" / "q1_20261020_6h" / "simulation_edgedata_20261020_6h.xml"),
                        help="Đường dẫn file simulation_edgedata.xml")
    parser.add_argument("--summary", "-s", type=str, default=None,
                        help="Đường dẫn file simulation_summary.xml (tùy chọn)")
    parser.add_argument("--outdir", "-o", type=str,
                        default=str(SCRIPT_DIR / "reports"),
                        help="Thư mục xuất báo cáo")
    parser.add_argument("--title", "-t", type=str, default="Kịch bản Quận 1 (20/10)",
                        help="Tiêu đề kịch bản")
    args = parser.parse_args()

    run_evaluation_level1(
        counts_xml=Path(args.counts),
        edgedata_xml=Path(args.edgedata),
        summary_xml=Path(args.summary) if args.summary else None,
        output_dir=Path(args.outdir),
        scenario_title=args.title
    )
