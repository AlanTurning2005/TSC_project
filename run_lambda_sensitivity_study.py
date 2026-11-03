r"""
run_lambda_sensitivity_study.py
=============================================================================
CHƯƠNG TRÌNH KHẢO SÁT ĐỘ NHẠY THAM SỐ NHU CẦU LAMBDA (LAMBDA SENSITIVITY STUDY)
Mô phỏng 2 Giờ (16:00 - 18:00) + 15 Phút Khởi động (Warm-up) trên Mạng lưới Q1-Q3
Đối chuẩn với Dữ liệu TomTom Dense 1-Minute ngày 2026-10-30

Các mức lambda kiểm tra: [1.8, 2.2, 2.6, 3.0, 3.4] veh/s
=============================================================================
"""

import os
import sys
import time
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple

# Cấu hình UTF-8 trên Windows
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
import seaborn as sns
from scipy import stats

# Đường dẫn dự án
PROJECT_ROOT = Path(__file__).resolve().parent
SUMO_BRIDGE_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "04_sumo_bridge"
EVAL_DIR = PROJECT_ROOT / "evaluation" / "level1_macro_flow"

for p in [PROJECT_ROOT, SUMO_BRIDGE_DIR, EVAL_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from generate_synthetic_demand import generate_synthetic_routes

# Cấu hình kịch bản
SCENARIO_DIR = PROJECT_ROOT / "sumo_scenarios" / "lambda_sensitivity_sweep"
REPORT_DIR = PROJECT_ROOT / "evaluation" / "reports" / "lambda_sensitivity"
SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

NET_FILE = PROJECT_ROOT / "data" / "raw_data" / "q1_map.net.xml"
VTYPES_FILE = PROJECT_ROOT / "data" / "raw_data" / "vtypes.add.xml"
TOMTOM_CSV = PROJECT_ROOT / "macro_traffic_crawler" / "data" / "processed" / "macro_traffic_dense_1min.csv"

# Thời gian mô phỏng
WARMUP_SECONDS = 900.0   # 15 phút khởi động
EVAL_SECONDS = 7200.0    # 2 giờ đo đạc (16:00 - 18:00)
TOTAL_SECONDS = WARMUP_SECONDS + EVAL_SECONDS  # 8100s

LAMBDA_LEVELS = [1.8, 2.2, 2.6, 3.0, 3.4]


def step1_generate_routes(rate: float) -> Path:
    """Sinh file route tổng hợp cho một mức lambda."""
    out_rou = SCENARIO_DIR / f"routes_lambda_{rate:.1f}.rou.xml"
    print(f"[*] Bắt đầu sinh lộ trình cho lambda = {rate:.1f} veh/s...")
    t0 = time.time()
    generate_synthetic_routes(
        net_file=NET_FILE,
        output_rou_file=out_rou,
        vtypes_file=VTYPES_FILE,
        insertion_rate_vps=rate,
        begin_time=0.0,
        end_time=TOTAL_SECONDS,
        fringe_factor=8.0,
        min_distance=400.0,
        speed_exponent=1.0,
        seed=42,
        verbose=False,
    )
    print(f"[+] Hoàn tất sinh lộ trình lambda = {rate:.1f} trong {time.time() - t0:.2f}s")
    return out_rou


def step2_run_sumo_simulation(rate: float) -> Dict[str, Any]:
    """Chạy một kịch bản SUMO cho một mức lambda."""
    rou_file = SCENARIO_DIR / f"routes_lambda_{rate:.1f}.rou.xml"
    add_file = SCENARIO_DIR / f"add_lambda_{rate:.1f}.xml"
    edgedata_file = SCENARIO_DIR / f"edgedata_lambda_{rate:.1f}.xml"
    tripinfo_file = SCENARIO_DIR / f"tripinfo_lambda_{rate:.1f}.xml"

    # Tạo tệp additional định nghĩa edgeData bắt đầu từ sau warm-up (t = 900s)
    add_xml_content = f"""<additional>
    <edgeData id="ed_eval_{rate:.1f}" file="{edgedata_file.name}" begin="{WARMUP_SECONDS:.0f}" end="{TOTAL_SECONDS:.0f}" freq="60"/>
</additional>"""
    with open(add_file, "w", encoding="utf-8") as f:
        f.write(add_xml_content)

    cmd = [
        "sumo",
        "-n", str(NET_FILE),
        "-r", str(rou_file),
        "-a", str(add_file),
        "--begin", "0",
        "--end", str(int(TOTAL_SECONDS)),
        "--step-length", "0.2",
        "--lateral-resolution", "0.25",
        "--time-to-teleport", "120",
        "--collision.action", "warn",
        "--no-step-log", "true",
        "--tripinfo-output", str(tripinfo_file),
    ]

    print(f"[*] [Lambda {rate:.1f}] Bắt đầu chạy mô phỏng SUMO (8100s, step 0.2s, sublane 0.25m)...")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(SCENARIO_DIR), capture_output=True, text=True)
    sim_time = time.time() - t0

    if res.returncode != 0:
        print(f"[!] [Lambda {rate:.1f}] Lỗi mô phỏng:\n{res.stderr}")
        raise RuntimeError(f"SUMO thất bại tại lambda={rate:.1f}: {res.stderr}")

    print(f"[+] [Lambda {rate:.1f}] Mô phỏng hoàn tất trong {sim_time:.1f}s ({sim_time / 60:.2f} phút)")
    return {
        "rate": rate,
        "sim_time_s": sim_time,
        "edgedata_file": str(edgedata_file),
        "tripinfo_file": str(tripinfo_file),
    }


def parse_edgedata(xml_path: Path) -> pd.DataFrame:
    """Trích xuất space-mean speed từ edgedata XML của SUMO."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    records = []
    for interval in root.findall("interval"):
        for edge in interval.findall("edge"):
            edge_id = edge.get("id", "")
            if not edge_id or edge_id.startswith(":"):
                continue
            speed_ms = float(edge.get("speed", "0.0"))
            sampled_sec = float(edge.get("sampledSeconds", "0.0"))
            clean_id = edge_id.lstrip("-").split("#")[0]
            point_id = f"way_{clean_id}"
            records.append({
                "point_id": point_id,
                "speed_ms": speed_ms,
                "sampled_seconds": sampled_sec,
            })

    if not records:
        return pd.DataFrame(columns=["point_id", "v_sim_kmh", "sampled_seconds"])

    df = pd.DataFrame(records)
    grouped = []
    for pid, group in df.groupby("point_id"):
        tot_sec = group["sampled_seconds"].sum()
        if tot_sec > 0:
            v_mean_ms = (group["speed_ms"] * group["sampled_seconds"]).sum() / tot_sec
        else:
            v_mean_ms = group["speed_ms"].mean()
        grouped.append({
            "point_id": pid,
            "v_sim_kmh": round(v_mean_ms * 3.6, 2),
            "sampled_seconds": round(tot_sec, 2),
        })
    return pd.DataFrame(grouped)


def parse_tripinfo(xml_path: Path, warmup_sec: float = 900.0) -> Dict[str, Any]:
    """Trích xuất số liệu chuyến đi từ tripinfo XML, lọc bỏ thời gian warm-up."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    durations = []
    time_losses = []
    waiting_times = []
    route_lengths = []
    speeds = []
    total_trips = 0
    post_warmup_trips = 0

    for trip in root.findall("tripinfo"):
        total_trips += 1
        depart = float(trip.get("depart", "0.0"))
        # Lọc bỏ phương tiện khởi hành trong giai đoạn warm-up
        if depart < warmup_sec:
            continue

        post_warmup_trips += 1
        dur = float(trip.get("duration", "0.0"))
        tloss = float(trip.get("timeLoss", "0.0"))
        wait = float(trip.get("waitingTime", "0.0"))
        rlen = float(trip.get("routeLength", "0.0"))

        durations.append(dur)
        time_losses.append(tloss)
        waiting_times.append(wait)
        route_lengths.append(rlen)
        if dur > 0:
            speeds.append((rlen / dur) * 3.6)

    return {
        "total_completed_trips": total_trips,
        "post_warmup_completed_trips": post_warmup_trips,
        "mean_duration_s": float(np.mean(durations)) if durations else 0.0,
        "mean_time_loss_s": float(np.mean(time_losses)) if time_losses else 0.0,
        "mean_waiting_time_s": float(np.mean(waiting_times)) if waiting_times else 0.0,
        "mean_trip_speed_kmh": float(np.mean(speeds)) if speeds else 0.0,
        "mean_route_length_m": float(np.mean(route_lengths)) if route_lengths else 0.0,
    }


def load_tomtom_benchmark(csv_path: Path) -> pd.DataFrame:
    """Nạp dữ liệu thực nghiệm TomTom ngày 2026-10-30 khung 16:00 - 18:00."""
    df = pd.read_csv(csv_path)
    df = df[df["date"] == "2026-10-30"]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    mask = (df["timestamp"].dt.hour >= 16) & (df["timestamp"].dt.hour < 18)
    sub = df[mask].copy()

    agg_df = sub.groupby("point_id").agg({
        "current_speed_kmh": "mean",
        "free_flow_speed_kmh": "first",
        "confidence": "mean",
        "road_name": "first",
    }).reset_index().rename(columns={
        "current_speed_kmh": "v_obs_kmh",
        "free_flow_speed_kmh": "v_free_kmh",
        "confidence": "mean_confidence",
    })
    return agg_df


def compute_metrics(sim_df: pd.DataFrame, tt_df: pd.DataFrame) -> Dict[str, Any]:
    """Tính toán sai số vận tốc cấp độ 1 giữa SUMO và TomTom."""
    merged = pd.merge(tt_df, sim_df, on="point_id", how="inner")
    if merged.empty:
        raise ValueError("Không có điểm quan trắc nào khớp giữa TomTom và SUMO!")

    v_sim = merged["v_sim_kmh"].values
    v_obs = merged["v_obs_kmh"].values
    v_free = merged["v_free_kmh"].values

    err = v_sim - v_obs
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    bias = float(np.mean(err))
    mre = float(np.mean(np.abs(err) / np.maximum(v_free, 10.0))) * 100.0

    # Spearman rank correlation
    spearman_corr, _ = stats.spearmanr(v_sim, v_obs)

    # Wasserstein distance
    w1_dist = float(stats.wasserstein_distance(v_sim, v_obs))

    return {
        "matched_points": len(merged),
        "mean_v_obs_kmh": float(np.mean(v_obs)),
        "median_v_obs_kmh": float(np.median(v_obs)),
        "mean_v_sim_kmh": float(np.mean(v_sim)),
        "median_v_sim_kmh": float(np.median(v_sim)),
        "rmse_kmh": rmse,
        "mae_kmh": mae,
        "bias_kmh": bias,
        "mre_pct": mre,
        "spearman_rank_corr": float(spearman_corr) if not np.isnan(spearman_corr) else 0.0,
        "wasserstein_w1_kmh": w1_dist,
    }


def plot_summary_report(results: List[Dict[str, Any]], tt_df: pd.DataFrame, out_path: Path):
    """Vẽ đồ thị tổng hợp 4 Panel chuẩn IEEE."""
    sns.set_theme(style="whitegrid", font_scale=1.0)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=300)

    rates = [r["rate"] for r in results]
    rmses = [r["metrics"]["rmse_kmh"] for r in results]
    maes = [r["metrics"]["mae_kmh"] for r in results]
    v_sims = [r["metrics"]["mean_v_sim_kmh"] for r in results]
    v_obs = results[0]["metrics"]["mean_v_obs_kmh"]
    w1s = [r["metrics"]["wasserstein_w1_kmh"] for r in results]
    time_losses = [r["trips"]["mean_time_loss_s"] for r in results]
    completion_rates = [r["completion_rate_pct"] for r in results]

    # Panel 1: RMSE & MAE vs Lambda
    ax1 = axes[0, 0]
    ax1.plot(rates, rmses, marker="o", linewidth=2.2, color="#d95f02", label=r"$\mathrm{RMSE}_v$ (km/h)")
    ax1.plot(rates, maes, marker="s", linewidth=2.0, color="#7570b3", linestyle="--", label=r"$\mathrm{MAE}_v$ (km/h)")
    # Thêm mốc Free-flow RMSE
    v_free_mean = tt_df["v_free_kmh"].mean()
    free_rmse = np.sqrt(np.mean((tt_df["v_free_kmh"] - tt_df["v_obs_kmh"])**2))
    ax1.axhline(free_rmse, color="gray", linestyle=":", label=f"Free-flow Baseline ({free_rmse:.1f} km/h)")
    ax1.set_xlabel(r"Tốc độ nạp phương tiện $\lambda$ (veh/s)", fontweight="bold")
    ax1.set_ylabel("Sai số Vận tốc (km/h)", fontweight="bold")
    ax1.set_title("A. Sai số Vận tốc theo Quy mô Nhu cầu (Speed Errors vs $\lambda$)", fontweight="bold")
    ax1.legend(loc="upper right", frameon=True)

    # Panel 2: Mean Simulated Speed vs Observed TomTom
    ax2 = axes[0, 1]
    ax2.plot(rates, v_sims, marker="^", linewidth=2.2, color="#1b9e77", label=r"SUMO $\bar{v}_{\mathrm{sim}}$ (km/h)")
    ax2.axhline(v_obs, color="#e7298a", linestyle="-.", linewidth=2.0, label=f"TomTom Thực tế ({v_obs:.2f} km/h)")
    ax2.fill_between(rates, v_obs - 1.5, v_obs + 1.5, color="#e7298a", alpha=0.15, label=r"Dải Tin cậy Quan trắc $\pm 1.5$ km/h")
    ax2.set_xlabel(r"Tốc độ nạp phương tiện $\lambda$ (veh/s)", fontweight="bold")
    ax2.set_ylabel("Vận tốc Trung bình Mạng (km/h)", fontweight="bold")
    ax2.set_title("B. Đáp ứng Vận tốc Mạng so với Thực tế (Mean Speed Response)", fontweight="bold")
    ax2.legend(loc="upper right", frameon=True)

    # Panel 3: Network Congestion & Time Loss
    ax3 = axes[1, 0]
    color_tl = "#386cb0"
    color_cr = "#e41a1c"
    ax3.plot(rates, time_losses, marker="D", linewidth=2.2, color=color_tl, label="Thời gian Trễ timeLoss (s)")
    ax3.set_xlabel(r"Tốc độ nạp phương tiện $\lambda$ (veh/s)", fontweight="bold")
    ax3.set_ylabel("Độ trễ trung bình / chuyến (giây)", color=color_tl, fontweight="bold")
    ax3.tick_params(axis="y", labelcolor=color_tl)

    ax3_twin = ax3.twinx()
    ax3_twin.plot(rates, completion_rates, marker="x", linewidth=2.0, color=color_cr, linestyle="--", label="Tỷ lệ hoàn thành (%)")
    ax3_twin.set_ylabel("Tỷ lệ Hoàn thành Chuyến đi (%)", color=color_cr, fontweight="bold")
    ax3_twin.tick_params(axis="y", labelcolor=color_cr)
    ax3.set_title("C. Động lực học Tắc nghẽn & Khả năng Thông hành", fontweight="bold")

    # Panel 4: Wasserstein Distance W1 (Distribution Divergence)
    ax4 = axes[1, 1]
    bars = ax4.bar([str(r) for r in rates], w1s, color="#4daf4a", alpha=0.8, edgecolor="black", width=0.5)
    ax4.set_xlabel(r"Tốc độ nạp phương tiện $\lambda$ (veh/s)", fontweight="bold")
    ax4.set_ylabel(r"Khoảng cách Wasserstein $W_1$ (km/h)", fontweight="bold")
    ax4.set_title("D. Độ tương đồng Phân bố Vận tốc ($W_1$ Metric)", fontweight="bold")
    for bar in bars:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width() / 2.0, yval + 0.1, f"{yval:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[+] Đã lưu đồ thị tổng hợp 4 panel tại: {out_path}")


def main():
    print("=" * 80)
    print("CHƯƠNG TRÌNH KHẢO SÁT ĐỘ NHẠY NHU CẦU LAMBDA TRÊN MẠNG LƯỚI QUẬN 1 & QUẬN 3")
    print(f"• Cửa sổ mô phỏng: 2 Giờ (7200s) + 15 Phút Khởi động (900s) = Tổng {TOTAL_SECONDS}s")
    print(f"• Bộ tham số lambda: {LAMBDA_LEVELS} veh/s")
    print("=" * 80)

    # Nạp dữ liệu TomTom chuẩn
    print("[*] Đang nạp dữ liệu kiểm chuẩn TomTom ngày 2026-10-30 (16:00 - 18:00)...")
    tt_df = load_tomtom_benchmark(TOMTOM_CSV)
    print(f"[+] Đã nạp {len(tt_df)} điểm quan trắc. Vận tốc thực tế TB: {tt_df['v_obs_kmh'].mean():.2f} km/h")

    # Bước 1: Sinh route cho cả 5 mức song song hoặc tuần tự
    print("\n" + "=" * 50)
    print("BƯỚC 1: SINH CÁC TỆP LỘ TRÌNH TỔNG HỢP (.rou.xml)")
    print("=" * 50)
    for rate in LAMBDA_LEVELS:
        step1_generate_routes(rate)

    # Bước 2: Chạy 5 mô phỏng song song trên ProcessPoolExecutor
    print("\n" + "=" * 50)
    print("BƯỚC 2: CHẠY ĐỒNG THỜI 5 MÔ PHỎNG SUMO (PARALLEL EXECUTION)")
    print("=" * 50)
    sim_outputs = {}
    with ProcessPoolExecutor(max_workers=min(5, os.cpu_count() or 4)) as executor:
        future_to_rate = {executor.submit(step2_run_sumo_simulation, rate): rate for rate in LAMBDA_LEVELS}
        for future in as_completed(future_to_rate):
            rate = future_to_rate[future]
            try:
                res = future.result()
                sim_outputs[rate] = res
            except Exception as e:
                print(f"[!] Lỗi tại lambda={rate}: {e}")
                raise e

    # Bước 3: Đánh giá số liệu và tổng hợp kết quả
    print("\n" + "=" * 50)
    print("BƯỚC 3: ĐÁNH GIÁ SỐ LIỆU ĐỘNG LỰC HỌC & ĐỐI CHUẨN TOMTOM")
    print("=" * 50)
    summary_results = []
    for rate in sorted(LAMBDA_LEVELS):
        out_info = sim_outputs[rate]
        edgedata_p = Path(out_info["edgedata_file"])
        tripinfo_p = Path(out_info["tripinfo_file"])

        sim_df = parse_edgedata(edgedata_p)
        metrics = compute_metrics(sim_df, tt_df)
        trips = parse_tripinfo(tripinfo_p, warmup_sec=WARMUP_SECONDS)

        # Ước tính tổng số xe nạp vào trong cửa sổ 2 giờ (post-warmup)
        expected_eval_vehs = rate * EVAL_SECONDS
        completed_eval_vehs = trips["post_warmup_completed_trips"]
        completion_rate = (completed_eval_vehs / expected_eval_vehs) * 100.0

        item = {
            "rate": rate,
            "hourly_flow_vehh": int(rate * 3600),
            "sim_time_s": out_info["sim_time_s"],
            "expected_inserted_vehs": int(expected_eval_vehs),
            "completed_vehs": completed_eval_vehs,
            "completion_rate_pct": round(completion_rate, 2),
            "metrics": metrics,
            "trips": trips,
        }
        summary_results.append(item)
        print(f"• Lambda {rate:.1f} veh/s ({rate * 3600:.0f} veh/h):")
        print(f"    v_sim TB: {metrics['mean_v_sim_kmh']:.2f} km/h (v_obs: {metrics['mean_v_obs_kmh']:.2f} km/h) | RMSE: {metrics['rmse_kmh']:.2f} km/h | MAE: {metrics['mae_kmh']:.2f} km/h")
        print(f"    W1: {metrics['wasserstein_w1_kmh']:.2f} km/h | timeLoss: {trips['mean_time_loss_s']:.1f}s | Hoàn thành: {completion_rate:.1f}%")

    # Lưu kết quả JSON và CSV
    json_path = REPORT_DIR / "lambda_sensitivity_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=4, ensure_ascii=False)
    print(f"\n[+] Đã xuất file số liệu JSON: {json_path}")

    # Tạo bảng phẳng CSV
    flat_rows = []
    for r in summary_results:
        m = r["metrics"]
        t = r["trips"]
        flat_rows.append({
            "lambda_vps": r["rate"],
            "hourly_flow_vph": r["hourly_flow_vehh"],
            "mean_v_sim_kmh": m["mean_v_sim_kmh"],
            "mean_v_obs_kmh": m["mean_v_obs_kmh"],
            "rmse_kmh": m["rmse_kmh"],
            "mae_kmh": m["mae_kmh"],
            "bias_kmh": m["bias_kmh"],
            "mre_pct": m["mre_pct"],
            "spearman_rho": m["spearman_rank_corr"],
            "wasserstein_w1_kmh": m["wasserstein_w1_kmh"],
            "completed_trips": r["completed_vehs"],
            "completion_rate_pct": r["completion_rate_pct"],
            "mean_time_loss_s": t["mean_time_loss_s"],
            "mean_waiting_time_s": t["mean_waiting_time_s"],
            "sim_runtime_s": round(r["sim_time_s"], 1),
        })
    df_flat = pd.DataFrame(flat_rows)
    csv_path = REPORT_DIR / "lambda_sensitivity_metrics.csv"
    df_flat.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[+] Đã xuất file số liệu CSV: {csv_path}")

    # Vẽ đồ thị 4 panel
    fig_path = REPORT_DIR / "lambda_sensitivity_curve.png"
    plot_summary_report(summary_results, tt_df, fig_path)

    print("\n" + "=" * 80)
    print("[+] HOÀN TẤT THÍ NGHIỆM ĐỘ NHẠY LAMBDA THÀNH CÔNG!")
    print("=" * 80)


if __name__ == "__main__":
    main()
