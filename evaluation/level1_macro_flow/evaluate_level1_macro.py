r"""
evaluate_level1_macro.py
=============================================================================
ĐIỀU PHỐI VIÊN ĐÁNH GIÁ VĨ MÔ CẤP ĐỘ 1 (LEVEL 1 MACRO EVALUATOR)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận: macro_traffic_crawler/docs/SD_EVALUATION.md

Mô đun thực thi toàn bộ quy trình kiểm chuẩn khoa học:
1. Đọc tệp XML edgedata của SUMO (quy đổi từ m/s sang km/h và tính space-mean speed).
2. Tích hợp dữ liệu chuẩn TomTom qua baseline_engine (bộ lọc coverage EDA, trọng số 1/sigma^2(c)).
3. Tính toán 4 Trụ Cột Động học Vận tốc Độc lập qua speed_metrics.
4. Đối chuẩn với 3 mốc: Free-flow (v0), Historical Median, và Sàn nhiễu lý thuyết (Delta_noise / sqrt(2)).
5. Kiểm định thống kê Spatial Cluster Bootstrap theo Hành lang qua statistical_tester.
6. Xuất báo cáo cấu trúc:
   - reports/level1_metrics_summary.json
   - reports/level1_edge_details.csv
   - reports/level1_macro_report.png (Đồ thị 4 panel chuẩn IEEE)
=============================================================================
"""

import os
import sys
import argparse
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

# Cấu hình cache thư mục tạm cho Matplotlib để tránh lỗi EPERM trên Windows
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# Hỗ trợ UTF-8 trên console Windows
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import các mô đun kiểm chuẩn trong cùng gói
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from speed_metrics import evaluate_speed_dynamics_suite, classify_los
from baseline_engine import load_multiday_traffic_data, compute_lodo_benchmark_anchors, benchmark_simulation_performance
from statistical_tester import spatial_cluster_bootstrap


def parse_sumo_edgedata(xml_path: Union[str, Path]) -> pd.DataFrame:
    r"""
    Trích xuất và tổng hợp vận tốc trung bình không gian (Space-Mean Speed) từ tệp XML edgedata của SUMO.

    Quy ước tính toán:
      - Vận tốc trong SUMO edgedata có đơn vị m/s -> nhân 3.6 để chuyển sang km/h.
      - Map edge_id trong SUMO về point_id tương ứng của TomTom:
          way_id = "way_" + edge_id.lstrip('-').split('#')[0]
      - Tổng hợp các đoạn làn nhỏ (lanes/segments) của cùng một way theo trung bình không gian có trọng số sampledSeconds:
          \bar{v}_{\text{way}} = 3.6 \times \frac{\sum (\text{sampledSeconds} \cdot v_e)}{\sum \text{sampledSeconds}}

    Args:
        xml_path: Đường dẫn tới tệp XML edgedata (sinh bởi SUMO qua cờ --edgedata-output).

    Returns:
        DataFrame gồm các cột: ['point_id', 'v_sim_kmh', 'sampled_seconds', 'segment_count']
    """
    xml_file = Path(xml_path)
    if not xml_file.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp SUMO edgedata tại: {xml_file}")

    tree = ET.parse(xml_file)
    root = tree.getroot()

    records = []
    # Quét qua các thẻ interval trong meandata
    for interval in root.findall("interval"):
        for edge in interval.findall("edge"):
            edge_id = edge.get("id", "")
            # Bỏ qua các cạnh nội bộ của nút giao (internal edges bắt đầu bằng dấu ':')
            if not edge_id or edge_id.startswith(":"):
                continue

            speed_ms = float(edge.get("speed", "0.0"))
            sampled_sec = float(edge.get("sampledSeconds", "0.0"))

            # Tách định danh way OSM gốc
            clean_id = edge_id.lstrip("-").split("#")[0]
            point_id = f"way_{clean_id}"

            records.append({
                "point_id": point_id,
                "edge_id": edge_id,
                "speed_ms": speed_ms,
                "sampled_seconds": sampled_sec,
            })

    if not records:
        raise ValueError(f"Không tìm thấy dữ liệu cạnh hợp lệ trong tệp XML: {xml_file}")

    df_raw = pd.DataFrame(records)

    # Tổng hợp theo point_id
    grouped = []
    for pid, group in df_raw.groupby("point_id"):
        tot_sec = group["sampled_seconds"].sum()
        if tot_sec > 0:
            # Trung bình có trọng số theo thời gian xe lưu lại trên cạnh (Space-mean speed)
            v_mean_ms = (group["speed_ms"] * group["sampled_seconds"]).sum() / tot_sec
        else:
            # Nếu không có xe nạp vào đoạn đó, lấy trung bình số học tốc độ tối đa quy định
            v_mean_ms = group["speed_ms"].mean()

        v_sim_kmh = float(v_mean_ms * 3.6)
        grouped.append({
            "point_id": pid,
            "v_sim_kmh": round(v_sim_kmh, 2),
            "sampled_seconds": round(tot_sec, 2),
            "segment_count": len(group),
        })

    return pd.DataFrame(grouped)


def align_and_prepare_evaluation_data(
    sim_df: pd.DataFrame,
    benchmark_source: Union[str, List[str], Path],
    test_date: Optional[str] = None,
    min_confidence_floor: float = 0.40,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    r"""
    Liên kết dữ liệu mô phỏng SUMO với dữ liệu kiểm chuẩn TomTom thực nghiệm, áp dụng:
      1. Khảo sát độ phủ (Coverage EDA) để loại bỏ các cạnh thiếu thông tin probe.
      2. Gán trọng số nghịch đảo phương sai w_e = 1 / \sigma^2(c).
      3. Tính toán các baseline đối chứng (Free-flow v0, Historical Median, Sàn nhiễu lý thuyết).

    Returns:
        Tuple: (DataFrame dữ liệu khớp chi tiết theo từng cạnh, Dict kết quả baseline anchors)
    """
    # 1. Nạp và làm sạch dữ liệu đa ngày từ TomTom
    df_tt = load_multiday_traffic_data(
        sources=benchmark_source,
        min_confidence=min_confidence_floor,
        time_slice_minutes=15,
    )

    # 2. Tính toán các mốc tham chiếu LODO
    anchors = compute_lodo_benchmark_anchors(df_tt, test_day=test_date)
    eff_test_date = anchors["test_day"]

    # 3. Trích xuất quan trắc ngày Test
    test_day_df = df_tt[df_tt["date"] == eff_test_date].copy()
    if test_day_df.empty:
        raise ValueError(f"Không có bản ghi nào cho ngày test '{eff_test_date}'!")

    # Bổ sung bản đồ định danh đường từ metadata nếu có
    metadata_points_file = CURRENT_DIR.parent.parent / "macro_traffic_crawler" / "data" / "metadata" / "sampling_points.csv"
    if not metadata_points_file.exists():
        metadata_points_file = CURRENT_DIR.parent.parent / "macro_traffic_crawler" / "data" / "sampling_points.csv"
    point_to_road = {}
    if metadata_points_file.exists():
        try:
            sp_df = pd.read_csv(metadata_points_file)
            if "point_id" in sp_df.columns and "road_name" in sp_df.columns:
                point_to_road = dict(zip(sp_df["point_id"], sp_df["road_name"]))
        except Exception:
            pass

    agg_test = {
        "speed_kmh": "mean",
        "free_flow_kmh": "first",
        "confidence": "mean",
    }
    if "road_name" in test_day_df.columns:
        agg_test["road_name"] = "first"

    test_obs = test_day_df.groupby("point_id").agg(agg_test).reset_index().rename(columns={
        "speed_kmh": "v_obs_kmh",
        "free_flow_kmh": "v_free_kmh",
    })

    if "road_name" not in test_obs.columns or test_obs["road_name"].isna().any():
        test_obs["road_name"] = test_obs["point_id"].map(lambda pid: point_to_road.get(pid, pid))

    # 4. Tính Historical Median của tập Train theo point_id
    train_dates = anchors["train_dates"]
    df_train = df_tt[df_tt["date"].isin(train_dates)]
    if not df_train.empty:
        train_medians = df_train.groupby("point_id")["speed_kmh"].median().reset_index().rename(
            columns={"speed_kmh": "v_median_kmh"}
        )
    else:
        train_medians = test_obs[["point_id", "v_free_kmh"]].rename(columns={"v_free_kmh": "v_median_kmh"})

    merged = pd.merge(test_obs, train_medians, on="point_id", how="inner")

    # 5. Khớp với vận tốc mô phỏng của SUMO
    aligned = pd.merge(merged, sim_df[["point_id", "v_sim_kmh", "sampled_seconds"]], on="point_id", how="inner")

    if aligned.empty:
        raise ValueError("Không tìm thấy điểm đo chung nào giữa kết quả mô phỏng SUMO và dữ liệu TomTom!")

    # 6. Gán trọng số nghịch đảo phương sai w_e(c)
    aligned["inv_var_weight"] = 1.0 / (np.maximum(0.05, 1.05 - aligned["confidence"]) ** 2)

    # 7. Tính sai lệch và phân loại LOS
    aligned["diff_sim_obs"] = aligned["v_sim_kmh"] - aligned["v_obs_kmh"]
    aligned["abs_diff"] = np.abs(aligned["diff_sim_obs"])
    aligned["los_obs"] = classify_los(aligned["v_obs_kmh"].to_numpy(), aligned["v_free_kmh"].to_numpy())
    aligned["los_sim"] = classify_los(aligned["v_sim_kmh"].to_numpy(), aligned["v_free_kmh"].to_numpy())

    return aligned, anchors


def plot_four_panel_report(
    aligned_df: pd.DataFrame,
    metrics_summary: Dict[str, Any],
    anchors: Dict[str, Any],
    output_path: Union[str, Path],
) -> None:
    r"""
    Vẽ biểu đồ 4 Panel chuẩn ấn phẩm khoa học IEEE/TRB (300 DPI):
      - Panel (a): Đồ thị phân tán Vận tốc Quan sát vs Mô phỏng (kèm đường 45 độ và vùng bao sai số).
      - Panel (b): Phân bố xác suất tích lũy ECDF (v_obs vs v_sim vs v_median) và khoảng cách Wasserstein W1.
      - Panel (c): Biểu đồ cột đối chuẩn 3 Mốc & Sàn nhiễu lý thuyết (chỉ rõ Vùng chuẩn khoa học).
      - Panel (d): Phân bố sai số theo Cụm Hành lang (Boxplot sai số tuyệt đối theo từng trục đường lớn).
    """
    sns.set_theme(style="ticks", font_scale=1.0)
    fig, axes = plt.subplots(2, 2, figsize=(14, 11), dpi=300)

    # Palette chuẩn IEEE
    los_colors = {"C": "#d95f02", "S": "#e6ab02", "F": "#1b9e77"}
    los_labels = {"C": "Congested (C)", "S": "Slow (S)", "F": "Free-flow (F)"}

    # -------------------------------------------------------------------------
    # Panel (a): Observed vs Simulated Scatter Plot
    # -------------------------------------------------------------------------
    ax_a = axes[0, 0]
    for los_cat in ["C", "S", "F"]:
        sub = aligned_df[aligned_df["los_obs"] == los_cat]
        if not sub.empty:
            ax_a.scatter(
                sub["v_obs_kmh"],
                sub["v_sim_kmh"],
                c=los_colors[los_cat],
                label=los_labels[los_cat],
                alpha=0.85,
                edgecolors="k",
                linewidth=0.5,
                s=55,
            )

    max_v = max(aligned_df["v_obs_kmh"].max(), aligned_df["v_sim_kmh"].max()) + 5.0
    ax_a.plot([0, max_v], [0, max_v], "k--", lw=1.5, label="Identity (1:1 line)")
    ax_a.fill_between([0, max_v], [-5, max_v - 5], [5, max_v + 5], color="gray", alpha=0.15, label="±5 km/h tolerance")
    ax_a.set_xlim(0, max_v)
    ax_a.set_ylim(0, max_v)
    ax_a.set_xlabel("TomTom Observed Speed (km/h)", fontweight="bold")
    ax_a.set_ylabel("SUMO Simulated Speed (km/h)", fontweight="bold")
    ax_a.set_title(
        f"(a) Observed vs. Simulated Speed Scatter\n"
        f"RMSE: {metrics_summary['pillar1_speed_errors']['rmse']:.2f} km/h | "
        f"Spearman ρ: {metrics_summary['pillar2_rank_correlation']['spearman_rho']:.3f}",
        fontsize=11,
        fontweight="bold"
    )
    ax_a.legend(loc="upper left", frameon=True, fontsize=8)
    ax_a.grid(True, linestyle=":", alpha=0.6)

    # -------------------------------------------------------------------------
    # Panel (b): Empirical Cumulative Distribution (ECDF)
    # -------------------------------------------------------------------------
    ax_b = axes[0, 1]
    sorted_obs = np.sort(aligned_df["v_obs_kmh"])
    sorted_sim = np.sort(aligned_df["v_sim_kmh"])
    sorted_med = np.sort(aligned_df["v_median_kmh"])
    cdf_y = np.linspace(0, 1, len(aligned_df))

    ax_b.step(sorted_obs, cdf_y, label="TomTom Observed ECDF", color="#0072B2", lw=2.2)
    ax_b.step(sorted_sim, cdf_y, label="SUMO Simulated ECDF", color="#D55E00", lw=2.2, linestyle="--")
    ax_b.step(sorted_med, cdf_y, label="Historical Median ECDF", color="#7570B3", lw=1.5, linestyle=":")

    w1_dist = metrics_summary["pillar3_distribution_divergence"]["wasserstein_w1"]
    ax_b.set_xlabel("Speed (km/h)", fontweight="bold")
    ax_b.set_ylabel("Empirical CDF", fontweight="bold")
    ax_b.set_title(
        f"(b) Speed Distribution Geometry\n"
        f"Wasserstein W1: {w1_dist:.2f} km/h | "
        f"KS Statistic: {metrics_summary['pillar3_distribution_divergence']['ks_statistic_d']:.3f}",
        fontsize=11,
        fontweight="bold"
    )
    ax_b.legend(loc="lower right", frameon=True, fontsize=9)
    ax_b.grid(True, linestyle=":", alpha=0.6)

    # -------------------------------------------------------------------------
    # Panel (c): Benchmark Anchors & Scientific Validity Zone
    # -------------------------------------------------------------------------
    ax_c = axes[1, 0]
    rmse_free = anchors.get("freeflow_baseline_rmse_kmh", 10.0)
    rmse_median = anchors.get("historical_median_rmse_kmh", 4.0)
    rmse_sumo = metrics_summary["pillar1_speed_errors"]["rmse"]
    sigma_floor = anchors.get("theoretical_noise_floor_kmh", 2.0)
    delta_noise = anchors.get("delta_noise_kmh", 3.0)

    bench_labels = ["Free-flow\n(v0)", "Historical\nMedian", "SUMO\nModel", "Noise Floor\n(Delta_noise)", "True Sàn Nhiễu\n(σ_floor)"]
    bench_values = [rmse_free, rmse_median, rmse_sumo, delta_noise, sigma_floor]
    bar_colors = ["#999999", "#56B4E9", "#E69F00", "#CC79A7", "#009E73"]

    bars = ax_c.bar(bench_labels, bench_values, color=bar_colors, edgecolor="k", linewidth=0.8, width=0.55)
    for bar in bars:
        height = bar.get_height()
        ax_c.annotate(f"{height:.2f}",
                      xy=(bar.get_x() + bar.get_width() / 2, height),
                      xytext=(0, 3), textcoords="offset points",
                      ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Vẽ dải khoa học đạt chuẩn
    ax_c.axhspan(sigma_floor, delta_noise, color="#009E73", alpha=0.15, label="Scientific Validity Zone")
    ax_c.set_ylabel("RMSE (km/h)", fontweight="bold")
    ax_c.set_title(
        f"(c) Benchmark Anchors & Theoretical Noise Floor\n"
        f"Zone: [{sigma_floor:.2f}, {delta_noise:.2f}] km/h",
        fontsize=11,
        fontweight="bold"
    )
    ax_c.legend(loc="upper right", frameon=True, fontsize=8)
    ax_c.grid(True, axis="y", linestyle=":", alpha=0.6)

    # -------------------------------------------------------------------------
    # Panel (d): Corridor Error Distribution Boxplot
    # -------------------------------------------------------------------------
    ax_d = axes[1, 1]
    top_roads = aligned_df["road_name"].value_counts().head(7).index.tolist()
    sub_corridors = aligned_df[aligned_df["road_name"].isin(top_roads)].copy()

    if not sub_corridors.empty:
        sns.boxplot(
            data=sub_corridors,
            y="road_name",
            x="abs_diff",
            hue="road_name",
            ax=ax_d,
            legend=False,
            palette="Blues_r",
            fliersize=3,
            linewidth=1.0,
        )
        ax_d.set_xlabel("Absolute Speed Error |v_sim - v_obs| (km/h)", fontweight="bold")
        ax_d.set_ylabel("Major Corridor", fontweight="bold")
        ax_d.set_title(
            "(d) Speed Error Distribution by Corridor\n"
            "(Spatial Autocorrelation across Urban Arterials)",
            fontsize=11,
            fontweight="bold"
        )
        ax_d.grid(True, axis="x", linestyle=":", alpha=0.6)
    else:
        ax_d.text(0.5, 0.5, "Không đủ dữ liệu hành lang để vẽ boxplot", ha="center", va="center")

    plt.tight_layout()
    output_p = Path(output_path)
    output_p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_p, bbox_inches="tight")
    plt.close(fig)
    print(f"[+] Đã lưu báo cáo đồ họa 4 Panel tại: {output_p}")


def run_level1_evaluation(
    edgedata_path: Union[str, Path],
    benchmark_source: Union[str, List[str], Path],
    output_dir: Union[str, Path] = "evaluation/level1_macro_flow/reports",
    test_date: Optional[str] = None,
    min_confidence_floor: float = 0.40,
) -> Dict[str, Any]:
    r"""
    Thực thi quy trình kiểm định vĩ mô cấp độ 1 hoàn chỉnh từ A đến Z.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("[*] KHỞI ĐỘNG LEVEL 1 MACRO FLOW EVALUATION (SPEED-CALIBRATED TESTBED)")
    print("=" * 75)

    # 1. Trích xuất vận tốc mô phỏng từ SUMO
    print(f"\n[1/5] Đang đọc tệp SUMO edgedata XML: {edgedata_path}...")
    sim_df = parse_sumo_edgedata(edgedata_path)
    print(f"      + Tìm thấy {len(sim_df)} way độc lập được mô phỏng trong SUMO.")

    # 2. Liên kết dữ liệu và nạp baselines
    print(f"\n[2/5] Đang liên kết với dữ liệu kiểm chuẩn TomTom ({benchmark_source})...")
    aligned_df, anchors = align_and_prepare_evaluation_data(
        sim_df=sim_df,
        benchmark_source=benchmark_source,
        test_date=test_date,
        min_confidence_floor=min_confidence_floor,
    )
    print(f"      + Ngày kiểm định Test: {anchors['test_day']}")
    print(f"      + Số điểm đo chung đạt chuẩn kiểm chuẩn: {len(aligned_df)} điểm.")

    # 3. Tính toán 4 Trụ Cột Động học Vận tốc
    print("\n[3/5] Đang tính toán 4 Trụ Cột Động học Vận tốc Độc lập...")
    metrics_summary = evaluate_speed_dynamics_suite(
        v_sim=aligned_df["v_sim_kmh"].to_numpy(),
        v_obs=aligned_df["v_obs_kmh"].to_numpy(),
        v_free=aligned_df["v_free_kmh"].to_numpy(),
        weights=aligned_df["inv_var_weight"].to_numpy(),
    )

    # 4. Kiểm định Spatial Cluster Bootstrap theo Hành lang
    print("\n[4/5] Đang thực hiện Spatial Cluster Bootstrap theo Hành lang...")
    def _rmse_calc(sub_df: pd.DataFrame) -> float:
        return float(np.sqrt(np.mean((sub_df["v_sim_kmh"] - sub_df["v_obs_kmh"]) ** 2)))

    boot_res = spatial_cluster_bootstrap(
        data_df=aligned_df,
        metric_calculator=_rmse_calc,
        cluster_col="road_name",
        n_boot=1000,
        random_seed=42,
    )
    print(f"      + Bootstrap 95% CI cho RMSE toàn mạng: {boot_res['ci_formatted']} km/h (M={boot_res['n_clusters']} hành lang)")

    # Đánh giá vị trí sai số SUMO so với các mốc qua benchmark_simulation_performance
    rmse_sumo = metrics_summary["pillar1_speed_errors"]["rmse"]
    bench_eval = benchmark_simulation_performance(rmse_sumo, anchors)
    sci_status = bench_eval["verdict"]
    sci_message = bench_eval["status_message"]

    # 5. Xuất các báo cáo
    print("\n[5/5] Đang xuất báo cáo và biểu đồ chuẩn học thuật...")
    full_report_json = {
        "evaluation_name": "Level 1 Macro Flow Evaluation",
        "test_date": anchors["test_day"],
        "num_evaluated_points": len(aligned_df),
        "scientific_validity": {
            "status": sci_status,
            "message": sci_message,
            "sumo_rmse": round(rmse_sumo, 3),
            "benchmarks": bench_eval["benchmarks"],
            "acceptable_zone_range": anchors.get("acceptable_zone_range"),
        },
        "pillar1_speed_errors": metrics_summary["pillar1_speed_errors"],
        "pillar2_rank_correlation": metrics_summary["pillar2_rank_correlation"],
        "pillar3_distribution_divergence": metrics_summary["pillar3_distribution_divergence"],
        "pillar4_los_regimes": metrics_summary["pillar4_los_regimes"],
        "spatial_cluster_bootstrap": boot_res,
    }

    json_path = out_dir / "level1_metrics_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_report_json, f, indent=4, ensure_ascii=False)
    print(f"[+] Đã lưu tệp tổng kết JSON tại: {json_path}")

    csv_path = out_dir / "level1_edge_details.csv"
    aligned_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[+] Đã lưu tệp chi tiết từng cạnh tại: {csv_path}")

    fig_path = out_dir / "level1_macro_report.png"
    plot_four_panel_report(
        aligned_df=aligned_df,
        metrics_summary=metrics_summary,
        anchors=anchors,
        output_path=fig_path,
    )

    print("\n" + "=" * 75)
    print("[+] HOÀN TẤT ĐÁNH GIÁ VĨ MÔ CẤP ĐỘ 1!")
    print(f"    • Trạng thái khoa học: {sci_status}")
    print(f"    • Đánh giá: {sci_message}")
    print("=" * 75)

    return full_report_json


def main():
    parser = argparse.ArgumentParser(description="Đánh giá Vĩ mô Cấp độ 1 (Level 1 Macro Flow Evaluation) cho SUMO")
    parser.add_argument("--edgedata", type=str, default="sumo_scenarios/q1_20261020_6h/simulation_edgedata_20261020_6h.xml",
                        help="Đường dẫn tệp edgedata XML của SUMO")
    parser.add_argument("--benchmark-csv", type=str, default="macro_traffic_crawler/data/processed/*.csv",
                        help="Đường dẫn hoặc mẫu glob tệp dữ liệu kiểm chuẩn TomTom CSV")
    parser.add_argument("--test-date", type=str, default=None,
                        help="Ngày kiểm định Test (ví dụ: '2026-10-20'). Mặc định tự động chọn ngày mới nhất.")
    parser.add_argument("--output-dir", type=str, default="evaluation/level1_macro_flow/reports",
                        help="Thư mục xuất báo cáo")
    parser.add_argument("--min-confidence", type=float, default=0.40,
                        help="Ngưỡng sàn độ tin cậy TomTom (mặc định 0.40)")

    args = parser.parse_args()

    run_level1_evaluation(
        edgedata_path=args.edgedata,
        benchmark_source=args.benchmark_csv,
        output_dir=args.output_dir,
        test_date=args.test_date,
        min_confidence_floor=args.min_confidence,
    )


if __name__ == "__main__":
    main()
