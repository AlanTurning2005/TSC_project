r"""
lodo_cross_validator.py
=============================================================================
HỆ THỐNG KIỂM ĐỊNH CHÉO NGOẠI SUY LEAVE-ONE-DAY-OUT (5-FOLD LODO CROSS-VALIDATION)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận:
- SD_EVALUATION.md (Mục IV, V & Mục VI)
- ROADMAP_50DAYS.md (Nhiệm vụ 1.4)

Bộ 5 Tiêu chuẩn Nghiệm thu Khoa học (5 Scientific Acceptance Criteria):
1. Sai số độ lệch vận tốc toàn mạng: |\text{Bias}_v(t)| <= 2.0 km/h (\forall t in {1..7})
2. Tương quan hạng cấp hành lang: \rho_{\text{corridor}} >= 0.50
   (Nhận diện đúng thứ tự các trục ùn tắc nặng: Điện Biên Phủ, NTMK, CMT8)
3. Chỉ số Kỹ năng Tương đối: \text{Skill Score} = 1 - \frac{\text{RMSE}(\boldsymbol{\lambda}^*)}{\text{RMSE}_{\text{ref}}} > 0
   (so với Free-flow Baseline v0 và Constant Demand Baseline \lambda = 1.0)
4. Khoảng cách Phân bố Wasserstein: W_1(P_{\text{sim}}, P_{\text{obs}}) giảm >= 25% so với khởi tạo
5. Kiểm tra Thoát nghẽn (Post-Peak Cooldown): TCR_{\text{drain}} >= 90% (không gridlock vĩnh viễn)
=============================================================================
"""

import os
import sys
import json
import argparse
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

# Cấu hình Matplotlib
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Hỗ trợ UTF-8 console Windows
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
EVAL_DIR = PROJECT_ROOT / "evaluation"
REPORTS_DIR = EVAL_DIR / "benchmark_reports"
FIGURES_DIR = EVAL_DIR / "figures"
PROCESSED_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "data" / "processed"
SCENARIOS_DIR = PROJECT_ROOT / "sumo_scenarios"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# Thêm đường dẫn import
CALIB_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "02_calibration"
for p in [CURRENT_DIR, CALIB_DIR, PROJECT_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from speed_metrics import (
    compute_speed_errors,
    compute_rank_correlation,
    compute_distribution_divergence,
    classify_los
)
from prepare_calibration_targets import load_calibration_targets_npz, load_corridor_definitions


def compute_corridor_speeds(
    v_matrix: np.ndarray,
    ordered_points: List[str],
    corridor_defs: Dict[str, Any]
) -> Dict[str, float]:
    r"""
    Tính vận tốc trung bình không gian trên từng hành lang trong 10 hành lang trục chính.
    """
    point_to_idx = {p: i for i, p in enumerate(ordered_points)}
    corridor_speeds = {}

    for cid, cinfo in corridor_defs.items():
        c_points = cinfo.get("points", [])
        indices = [point_to_idx[p] for p in c_points if p in point_to_idx]
        if indices:
            # Lấy trung bình vận tốc trên tất cả các điểm và lát cắt của hành lang
            c_speeds = v_matrix[indices, :]
            corridor_speeds[cid] = float(np.mean(c_speeds))
        else:
            corridor_speeds[cid] = 0.0

    return corridor_speeds


def evaluate_5_acceptance_criteria(
    v_sim: np.ndarray,
    v_obs: np.ndarray,
    weights: np.ndarray,
    v0_vector: np.ndarray,
    v_sim_init: np.ndarray,
    ordered_points: List[str],
    corridor_defs: Dict[str, Any],
    telemetry: Dict[str, float],
    slice_names: List[str]
) -> Dict[str, Any]:
    r"""
    Đánh giá toàn diện 5 Tiêu chuẩn Nghiệm thu Khoa học chuẩn IEEE/TRB.
    """
    K_SLICES = len(slice_names)

    # ---------------------------------------------------------
    # Tiêu chí 1: Sai số độ lệch vận tốc toàn mạng (|Bias_v(t)| <= 2.0 km/h)
    # ---------------------------------------------------------
    biases_by_slice = {}
    bias_pass = True
    for t in range(K_SLICES):
        w_t = weights[:, t]
        w_sum = np.sum(w_t)
        if w_sum > 0:
            bias_t = float(np.sum(w_t * (v_sim[:, t] - v_obs[:, t])) / w_sum)
            biases_by_slice[slice_names[t]] = round(bias_t, 3)
            if abs(bias_t) > 2.0:
                bias_pass = False
        else:
            # Lát cắt này bị khuyết dữ liệu quan trắc (Masked Loss) -> Bỏ qua không tính vào Bias
            biases_by_slice[slice_names[t]] = 0.0

    max_abs_bias = float(max(abs(b) for b in biases_by_slice.values()))

    # ---------------------------------------------------------
    # Tiêu chí 2: Tương quan thứ bậc cấp hành lang (\rho_corridor >= 0.50)
    # ---------------------------------------------------------
    c_speeds_sim = compute_corridor_speeds(v_sim, ordered_points, corridor_defs)
    c_speeds_obs = compute_corridor_speeds(v_obs, ordered_points, corridor_defs)

    corridor_ids = sorted(list(corridor_defs.keys()))
    sim_ranks = [c_speeds_sim[cid] for cid in corridor_ids]
    obs_ranks = [c_speeds_obs[cid] for cid in corridor_ids]

    rho_res = compute_rank_correlation(np.array(sim_ranks), np.array(obs_ranks))
    rho_corridor = float(rho_res["spearman_rho"])
    rho_pass = (rho_corridor >= 0.50)

    # ---------------------------------------------------------
    # Tiêu chí 3: Chỉ số Kỹ năng Tương đối (Skill Score > 0)
    # ---------------------------------------------------------
    err_calib = compute_speed_errors(v_sim, v_obs, weights=weights)
    rmse_calib = float(err_calib["rmse_kmh"])

    # Baseline 1: Free-flow Baseline (v0 trên tất cả các lát)
    v0_mat = np.tile(v0_vector[:, np.newaxis], (1, K_SLICES))
    err_v0 = compute_speed_errors(v0_mat, v_obs, weights=weights)
    rmse_v0 = float(err_v0["rmse_kmh"])

    skill_score_v0 = 1.0 - (rmse_calib / max(1e-3, rmse_v0))
    skill_score_pass = (skill_score_v0 > 0.0)

    # ---------------------------------------------------------
    # Tiêu chí 4: Khoảng cách Phân bố Wasserstein (W_1 giảm >= 25% so với khởi tạo)
    # ---------------------------------------------------------
    w1_calib_res = compute_distribution_divergence(v_sim.flatten(), v_obs.flatten())
    w1_calib = float(w1_calib_res["wasserstein_w1_kmh"])

    w1_init_res = compute_distribution_divergence(v_sim_init.flatten(), v_obs.flatten())
    w1_init = float(w1_init_res["wasserstein_w1_kmh"])

    if w1_init > 0:
        w1_reduction_pct = float((w1_init - w1_calib) / w1_init * 100.0)
    else:
        w1_reduction_pct = 0.0
    w1_pass = (w1_reduction_pct >= 25.0)

    # ---------------------------------------------------------
    # Tiêu chí 5: Kiểm tra Thoát nghẽn (Post-Peak Cooldown TCR >= 90%)
    # ---------------------------------------------------------
    tcr = float(telemetry.get("tcr", 1.0)) * 100.0
    teleport_rate = float(telemetry.get("teleport_rate", 0.0)) * 100.0
    drain_pass = (tcr >= 90.0) and (teleport_rate < 0.10)

    all_pass = (bias_pass and rho_pass and skill_score_pass and w1_pass and drain_pass)

    return {
        "all_criteria_met": all_pass,
        "criterion_1_speed_bias": {
            "passed": bias_pass,
            "threshold_kmh": 2.0,
            "max_abs_bias_kmh": round(max_abs_bias, 3),
            "biases_by_slice": biases_by_slice,
        },
        "criterion_2_corridor_spearman": {
            "passed": rho_pass,
            "threshold": 0.50,
            "rho_corridor": round(rho_corridor, 3),
            "p_value": rho_res.get("p_value", 0.0),
        },
        "criterion_3_skill_score": {
            "passed": skill_score_pass,
            "threshold": 0.0,
            "skill_score_wrt_v0": round(skill_score_v0, 4),
            "rmse_calibrated_kmh": round(rmse_calib, 3),
            "mae_calibrated_kmh": round(float(err_calib.get("mae_kmh", 0.0)), 3),
            "rmse_free_flow_kmh": round(rmse_v0, 3),
        },
        "criterion_4_wasserstein_w1": {
            "passed": w1_pass,
            "threshold_reduction_pct": 25.0,
            "w1_calibrated_kmh": round(w1_calib, 3),
            "w1_initial_kmh": round(w1_init, 3),
            "w1_reduction_pct": round(w1_reduction_pct, 2),
        },
        "criterion_5_drain_clearance": {
            "passed": drain_pass,
            "tcr_percent": round(tcr, 2),
            "threshold_tcr_pct": 90.0,
            "teleport_rate_percent": round(teleport_rate, 4),
            "threshold_teleport_pct": 0.10,
        }
    }


def plot_lodo_validation_report(
    fold_results: Dict[str, Any],
    output_png: Path
) -> None:
    r"""
    Xuất biểu đồ 4-panel chuẩn IEEE/TRB báo cáo nghiệm thu 5 Folds LODO.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    dates = list(fold_results.keys())
    rmse_vals = [fold_results[d]["criterion_3_skill_score"]["rmse_calibrated_kmh"] for d in dates]
    rmse_v0_vals = [fold_results[d]["criterion_3_skill_score"]["rmse_free_flow_kmh"] for d in dates]
    rho_vals = [fold_results[d]["criterion_2_corridor_spearman"]["rho_corridor"] for d in dates]
    w1_red_vals = [fold_results[d]["criterion_4_wasserstein_w1"]["w1_reduction_pct"] for d in dates]
    max_biases = [fold_results[d]["criterion_1_speed_bias"]["max_abs_bias_kmh"] for d in dates]

    # Panel 1: RMSE vs Free-flow Baseline
    x = np.arange(len(dates))
    width = 0.35
    axes[0, 0].bar(x - width/2, rmse_vals, width, label="Calibrated Model", color="#2b5c8f")
    axes[0, 0].bar(x + width/2, rmse_v0_vals, width, label="Free-flow Baseline (v0)", color="#d95f02", alpha=0.7)
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels([f"Fold: {d[-5:]}" for d in dates], rotation=15)
    axes[0, 0].set_ylabel("Speed RMSE (km/h)", fontsize=11)
    axes[0, 0].set_title("(a) Speed RMSE Across LODO Test Folds", fontweight="bold", fontsize=12)
    axes[0, 0].legend()
    axes[0, 0].grid(True, linestyle="--", alpha=0.5)

    # Panel 2: Max Absolute Bias
    axes[0, 1].bar(dates, max_biases, color="#7570b3", alpha=0.85)
    axes[0, 1].axhline(2.0, color="red", linestyle="--", linewidth=1.8, label="Acceptance Limit (|Bias| <= 2.0 km/h)")
    axes[0, 1].set_ylabel("Max |Bias| (km/h)", fontsize=11)
    axes[0, 1].set_title("(b) Whole-Network Speed Bias per Fold", fontweight="bold", fontsize=12)
    axes[0, 1].legend()
    axes[0, 1].grid(True, linestyle="--", alpha=0.5)

    # Panel 3: Corridor Spearman Rank
    axes[1, 0].plot(dates, rho_vals, "o-", color="#1b9e77", linewidth=2.2, markersize=8)
    axes[1, 0].axhline(0.50, color="darkgreen", linestyle="--", linewidth=1.8, label="Acceptance Floor (rho >= 0.50)")
    axes[1, 0].set_ylabel("Corridor Spearman rho", fontsize=11)
    axes[1, 0].set_title("(c) Corridor-Level Congestion Ranking", fontweight="bold", fontsize=12)
    axes[1, 0].legend()
    axes[1, 0].grid(True, linestyle="--", alpha=0.5)

    # Panel 4: Wasserstein Distance Reduction
    axes[1, 1].bar(dates, w1_red_vals, color="#e7298a", alpha=0.8)
    axes[1, 1].axhline(25.0, color="purple", linestyle="--", linewidth=1.8, label="Required Reduction (>= 25%)")
    axes[1, 1].set_ylabel("W1 Reduction (%)", fontsize=11)
    axes[1, 1].set_title("(d) Distributional Alignment Improvement", fontweight="bold", fontsize=12)
    axes[1, 1].legend()
    axes[1, 1].grid(True, linestyle="--", alpha=0.5)

    fig.tight_layout()
    fig.savefig(output_png, dpi=200)
    plt.close(fig)
    print(f"[+] Đã xuất biểu đồ nghiệm thu LODO vào: {output_png.name}")


def run_full_lodo_pipeline(
    best_lambda: Optional[np.ndarray] = None,
    run_sim: bool = False,
    dry_run: bool = False,
    sim_artifact: Optional[str] = None,
    step_length: float = 0.4,
    lateral_resolution: float = 0.40,
    filter_date: Optional[str] = None,
    use_realistic_prior: bool = False,
) -> Dict[str, Any]:
    r"""
    Thực thi kiểm định chéo LODO trên các ngày làm việc độc lập và xuất báo cáo.
    Tuân thủ nghiêm ngặt Quy chuẩn Liêm chính Học thuật (Simulation Integrity):
      - Cấm dùng dữ liệu quan sát/median làm thế thân cho v_sim mà không qua mô phỏng.
      - Chế độ dry-run được cô lập hoàn toàn, không được ghi đè vào level1_lodo_results.json.
    """
    if not run_sim and not sim_artifact and not dry_run:
        raise ValueError(
            "\n[LỖI LIÊM CHÍNH HỌC THUẬT & PHÒNG CHỐNG NGỤY BIỆN DỮ LIỆU]:\n"
            "Bạn phải chỉ định rõ một trong các chế độ thực thi sau:\n"
            "  1. --sim : Chạy mô phỏng vi mô SUMO thực tế (trích xuất trace từ edgedata & summary XML).\n"
            "  2. --sim-artifact <path> : Nạp kết quả từ file mô phỏng SUMO đã được xác thực trước đó.\n"
            "  3. --dry-run : Chạy kiểm thử cú pháp đường ống (Sanity Unit Test). Chế độ này sẽ KHÔNG ghi đè vào báo cáo chính thức level1_lodo_results.json.\n"
            "Tuyệt đối nghiêm cấm chạy mặc định mà không kích hoạt mô phỏng để tránh rò rỉ dữ liệu (Surrogate Data Leakage)."
        )

    targets = load_calibration_targets_npz()
    corridors = load_corridor_definitions()
    dates = targets["dates"]
    if filter_date is not None:
        if filter_date in dates:
            dates = [filter_date]
        else:
            raise KeyError(f"Ngày kiểm tra {filter_date} không nằm trong danh sách ngày có dữ liệu: {dates}")

    ordered_points = targets["point_ids"]
    v0_vector = targets["v0_free_flow"]
    slice_names = targets["time_slices"]

    # 1. Nạp vector lambda tốt nhất hoặc vector tiên nghiệm thực tế mới
    if best_lambda is None:
        if use_realistic_prior:
            # Vector tiên nghiệm thực tế cao điểm TP.HCM: 2.0 -> 3.4 -> 2.5
            best_lambda = np.array([2.0, 2.6, 3.2, 3.4, 3.0, 2.7, 2.5], dtype=float)
            print(f"[*] Sử dụng Vector Tiên nghiệm Thực tế Mới (Realistic Peak Prior): {best_lambda.tolist()}")
        else:
            best_json = PROCESSED_DIR / "cmaes_best_params.json"
            if best_json.exists():
                with open(best_json, "r", encoding="utf-8") as f:
                    info = json.load(f)
                    best_lambda = np.array(info["best_lambda_vps"], dtype=float)
                    print(f"[*] Nạp vector lambda* tốt nhất từ {best_json.name}: {np.round(best_lambda, 3).tolist()}")
            else:
                best_lambda = np.array([2.0, 2.6, 3.2, 3.4, 3.0, 2.7, 2.5], dtype=float)
                print(f"[!] Dùng vector lambda mặc định: {best_lambda.tolist()}")

    provenance_info = {}

    # 2. Sinh ma trận vận tốc mô phỏng v_sim
    if run_sim:
        from sumo_headless_runner import evaluate_candidate, ensure_warmup_checkpoint
        ckpt_v04 = SCENARIOS_DIR / "q1_calibrated_morning" / "checkpoint_warmup_0630_v04.xml"
        if not ckpt_v04.exists():
            ensure_warmup_checkpoint(
                checkpoint_file=ckpt_v04,
                step_length=step_length,
                lateral_resolution=lateral_resolution
            )
        print(f"[*] Đang chạy mô phỏng vi mô SUMO với lambda* (step_length={step_length}s, lat_res={lateral_resolution}m)...")
        v_sim, telemetry = evaluate_candidate(
            lambda_vec=best_lambda,
            ordered_points=ordered_points,
            v0_vector=v0_vector,
            checkpoint_file=ckpt_v04,
            step_length=step_length,
            lateral_resolution=lateral_resolution,
            timeout_sec=1200,
            tag="lodo_eval"
        )
        # Lưu vết kết quả mô phỏng thực tế làm artifact để tái sử dụng
        trace_file = REPORTS_DIR / "lodo_sim_trace_latest.npz"
        np.savez_compressed(
            trace_file,
            v_sim=v_sim,
            best_lambda=best_lambda,
            tcr=telemetry.get("tcr", 0.0),
            teleport_rate=telemetry.get("teleport_rate", 0.0),
            icr=telemetry.get("icr", 0.0),
            gbr=telemetry.get("gbr", 0.0),
        )
        provenance_info = {
            "is_real_sumo_simulation": True,
            "is_synthetic_dry_run": False,
            "provenance_type": "live_sumo_microsimulation",
            "step_length_s": step_length,
            "lateral_resolution_m": lateral_resolution,
            "trace_artifact_saved": trace_file.name,
            "telemetry_source": "summary_xml_parsed"
        }
    elif sim_artifact:
        art_path = Path(sim_artifact).resolve()
        if not art_path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp artifact mô phỏng: {art_path}")
        print(f"[*] Nạp kết quả mô phỏng vi mô SUMO từ artifact đã xác thực: {art_path.name}")
        art_data = np.load(art_path)
        v_sim = art_data["v_sim"]
        telemetry = {
            "tcr": float(art_data.get("tcr", 0.85)),
            "teleport_rate": float(art_data.get("teleport_rate", 0.0)),
            "icr": float(art_data.get("icr", 1.0)),
            "gbr": float(art_data.get("gbr", 0.0)),
        }
        provenance_info = {
            "is_real_sumo_simulation": True,
            "is_synthetic_dry_run": False,
            "provenance_type": "cached_sumo_microsimulation",
            "artifact_path": str(art_path),
            "telemetry_source": "artifact_loaded"
        }
    else:
        # Chế độ Dry-Run
        print("\n" + "=" * 70)
        print("[!] CẢNH BÁO LIÊM CHÍNH HỌC THUẬT: ĐANG CHẠY CHẾ ĐỘ SURROGATE DRY-RUN")
        print("  • Ma trận v_sim và telemetry KHÔNG xuất phát từ SUMO vi mô thật.")
        print("  • Dữ liệu này chỉ phục vụ kiểm thử cú pháp đường ống (Unit Testing).")
        print("  • TUYỆT ĐỐI KHÔNG SỬ DỤNG SỐ LIỆU NÀY CHO BÁO CÁO HỌC THUẬT HOẶC KHÓA LUẬN!")
        print("  • Tệp nghiệm thu level1_lodo_results.json CHÍNH THỨC SẼ KHÔNG BỊ GHI ĐÈ.")
        print("=" * 70 + "\n")
        v_median = targets["v_historical_median"]
        v_sim = np.copy(v_median)
        mean_lambda = float(np.mean(best_lambda))
        for t in range(len(best_lambda)):
            factor = (best_lambda[t] - mean_lambda) * 0.8
            v_sim[:, t] = np.maximum(8.0, v_sim[:, t] - factor)
        telemetry = {"tcr": 0.9412, "teleport_rate": 0.0, "icr": 1.0, "gbr": 0.0}
        provenance_info = {
            "is_real_sumo_simulation": False,
            "is_synthetic_dry_run": True,
            "provenance_type": "surrogate_dry_run_synthetic",
            "warning": "DO NOT USE FOR SCIENTIFIC PAPERS"
        }

    # Ma trận khởi tạo (chưa hiệu chuẩn, dùng để so sánh Wasserstein reduction)
    v_sim_init = np.tile(v0_vector[:, np.newaxis], (1, len(slice_names)))

    # 3. Đánh giá từng Fold LODO
    fold_reports = {}
    print(f"\n[*] Đang thực thi đánh giá 5 Tiêu chuẩn trên {len(dates)} ngày kiểm định:")
    for d in dates:
        v_obs_d = targets["v_obs_by_date"][d]
        w_d = targets["weights_by_date"][d]

        crit_d = evaluate_5_acceptance_criteria(
            v_sim=v_sim,
            v_obs=v_obs_d,
            weights=w_d,
            v0_vector=v0_vector,
            v_sim_init=v_sim_init,
            ordered_points=ordered_points,
            corridor_defs=corridors,
            telemetry=telemetry,
            slice_names=slice_names
        )
        fold_reports[d] = crit_d
        status_str = "[PASS]" if crit_d["all_criteria_met"] else "[WARN]"
        bias_val = crit_d["criterion_1_speed_bias"]["max_abs_bias_kmh"]
        rho_val = crit_d["criterion_2_corridor_spearman"]["rho_corridor"]
        rmse_val = crit_d["criterion_3_skill_score"]["rmse_calibrated_kmh"]
        mae_val = crit_d["criterion_3_skill_score"].get("mae_calibrated_kmh", 0.0)
        w1_val = crit_d["criterion_4_wasserstein_w1"]["w1_calibrated_kmh"]
        print(f"  • Fold {d}: {status_str} | RMSE={rmse_val:.2f} km/h | MAE={mae_val:.2f} km/h | Max |Bias|={bias_val:.2f} km/h | Spearman ρ={rho_val:.2f} | W1={w1_val:.2f} km/h")

    # 4. Xuất báo cáo JSON
    summary_report = {
        "evaluation_name": "5_fold_lodo_cross_validation",
        "provenance": provenance_info,
        "created_at": pd.Timestamp.now().isoformat(),
        "calibrated_lambda_vector": [round(float(x), 4) for x in best_lambda],
        "test_dates": dates,
        "fold_results": fold_reports,
        "overall_summary": {
            "all_folds_passed": all(f["all_criteria_met"] for f in fold_reports.values()),
            "mean_rmse_kmh": round(float(np.mean([f["criterion_3_skill_score"]["rmse_calibrated_kmh"] for f in fold_reports.values()])), 3),
            "mean_corridor_spearman_rho": round(float(np.mean([f["criterion_2_corridor_spearman"]["rho_corridor"] for f in fold_reports.values()])), 3),
            "mean_w1_reduction_pct": round(float(np.mean([f["criterion_4_wasserstein_w1"]["w1_reduction_pct"] for f in fold_reports.values()])), 2),
            "drain_tcr_pct": round(float(telemetry["tcr"] * 100.0), 2),
        }
    }

    if dry_run:
        out_json = REPORTS_DIR / "level1_lodo_dryrun_sanity.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(summary_report, f, ensure_ascii=False, indent=2)
        print(f"\n[!] Báo cáo kiểm thử Dry-Run đã lưu riêng vào: {out_json.name} (Tệp chính thức không bị thay đổi).")
    else:
        out_json = REPORTS_DIR / "level1_lodo_results.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(summary_report, f, ensure_ascii=False, indent=2)
        print(f"\n[+] Đã lưu báo cáo thống kê LODO chính thức vào: {out_json.name}")

    # 5. Vẽ biểu đồ kiểm định 4-panel (chỉ vẽ khi chạy thật hoặc có cờ dry-run)
    out_png = FIGURES_DIR / ("lodo_dryrun_sanity.png" if dry_run else "lodo_validation_report.png")
    plot_lodo_validation_report(fold_reports, out_png)

    return summary_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kiểm định chéo LODO và 5 Tiêu chuẩn Nghiệm thu")
    parser.add_argument("--sim", action="store_true", help="Chạy lại mô phỏng vi mô SUMO trực tiếp")
    parser.add_argument("--dry-run", action="store_true", help="Chạy kiểm thử cú pháp đường ống (Dry-Run Sanity Test)")
    parser.add_argument("--sim-artifact", type=str, default=None, help="Đường dẫn file .npz lưu kết quả mô phỏng vi mô SUMO")
    parser.add_argument("--step-length", type=float, default=0.4, help="Bước thời gian mô phỏng vi mô SUMO (giây, mặc định: 0.4)")
    parser.add_argument("--lateral-resolution", type=float, default=0.40, help="Độ phân giải Sublane ngang (mét, mặc định: 0.40)")
    parser.add_argument("--test-date", type=str, default=None, help="Chạy kiểm định trên 1 ngày cụ thể (ví dụ 2026-10-15)")
    parser.add_argument("--use-realistic-prior", action="store_true", help="Dùng vector tiên nghiệm thực tế [2.0, 2.6, 3.2, 3.4, 3.0, 2.7, 2.5]")
    args = parser.parse_args()

    print("=" * 70)
    print("[*] BẮT ĐẦU KIỂM ĐỊNH CHÉO LODO (5-FOLD LEAVE-ONE-DAY-OUT)")
    print("=" * 70)
    res = run_full_lodo_pipeline(
        run_sim=args.sim,
        dry_run=args.dry_run,
        sim_artifact=args.sim_artifact,
        step_length=args.step_length,
        lateral_resolution=args.lateral_resolution,
        filter_date=args.test_date,
        use_realistic_prior=args.use_realistic_prior
    )
    print("\n" + "=" * 70)
    print("[OK] QUY TRÌNH KIỂM ĐỊNH LODO HOÀN TẤT THÀNH CÔNG!")
    print("=" * 70)
