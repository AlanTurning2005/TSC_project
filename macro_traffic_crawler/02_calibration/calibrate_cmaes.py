r"""
calibrate_cmaes.py
=============================================================================
PIPELINE TỐI ƯU HÓA NHU CẦU ĐỘNG HỌC SONG SONG QUA CMA-ES (PARALLEL CMA-ES)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận:
- SD_EVALUATION.md (Mục 2.2, 2.3 & Mục IV)
- ROADMAP_50DAYS.md (Nhiệm vụ 1.2)

Các tính năng kỹ thuật cốt lõi:
1. Sử dụng thuật toán CMA-ES (Covariance Matrix Adaptation Evolution Strategy)
   thông qua Optuna CmaEsSampler (bản port tối ưu của Hansen CMA-ES).
2. Tối ưu hóa đồng thời 7 chiều nhu cầu: \boldsymbol{\lambda} \in [0.10, 3.00]^7.
3. Chạy song song N_WORKERS = 3 hoặc 4 tiến trình với quyền ưu tiên thấp
   (BELOW_NORMAL_PRIORITY_CLASS), bảo toàn 8-9 logical cores cho hệ điều hành và IDE.
4. Cơ chế lưu trữ bền vững (SQLite Storage) cho phép phục hồi (resume) nếu bị ngắt.
5. Hàm mục tiêu điều chuẩn trơn vi phân bậc 2 kết hợp Tiên nghiệm HOUTRANS TP.HCM
   và Rào chắn BPR phi thứ nguyên (chuẩn hóa 2 bước xử lý w_pen).
6. Tích hợp Checkpoint Warm-up 06:30 giúp bỏ qua 1.800s mô phỏng ở mọi cá thể.
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
import optuna
from optuna.samplers import CmaEsSampler

# Cấu hình cache thư mục tạm cho Matplotlib
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Hạ mức ưu tiên tiến trình (Below Normal)
try:
    import psutil
    _p = psutil.Process()
    if sys.platform == "win32":
        _p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    else:
        _p.nice(10)
except Exception:
    pass

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
METADATA_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "data" / "metadata"
PROCESSED_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "data" / "processed"
SCENARIOS_DIR = PROJECT_ROOT / "sumo_scenarios"

# Import các tiện ích nội bộ
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from prepare_calibration_targets import load_calibration_targets_npz
from sumo_headless_runner import (
    evaluate_candidate,
    evaluate_candidate_crn,
    ensure_warmup_checkpoint,
    load_point_ids,
)

# Trọng số giờ cao điểm HOUTRANS TP.HCM cho 7 lát cắt (06:30 - 10:00)
HOUTRANS_PEAK_SLICES = {
    "06:30": 0.85,
    "07:00": 1.25,
    "07:30": 1.50, # Đỉnh cao điểm sáng
    "08:00": 1.35,
    "08:30": 1.10,
    "09:00": 0.90,
    "09:30": 0.85,
}

# Vector Tiên nghiệm Cao điểm Sáng Thực tế TP.HCM (Realistic HCMC Morning Peak Prior)
# Khởi điểm 2.0 veh/s (06:30) -> Đỉnh 3.2 - 3.4 veh/s (07:30 - 08:30) -> Giảm nhẹ 2.5 - 2.7 veh/s (09:00 - 10:00)
REALISTIC_HCMC_PEAK_PRIOR = {
    "06:30": 2.00,
    "07:00": 2.60,
    "07:30": 3.20,
    "08:00": 3.40,
    "08:30": 3.00,
    "09:00": 2.70,
    "09:30": 2.50,
}


def build_houtrans_prior_7slices(base_rate_vps: float = 1.0) -> np.ndarray:
    """Xây dựng vector hình dáng tiên nghiệm HOUTRANS gốc cho 7 lát cắt (xe/giây)."""
    weights = [HOUTRANS_PEAK_SLICES[ts] for ts in ["06:30", "07:00", "07:30", "08:00", "08:30", "09:00", "09:30"]]
    return np.array(weights, dtype=float) * base_rate_vps


def build_realistic_peak_prior_7slices(base_rate_vps: float = 1.0) -> np.ndarray:
    """Xây dựng vector hình dáng tiên nghiệm cao điểm TP.HCM thực tế cho 7 lát cắt (2.0 -> 3.4 -> 2.5 veh/s)."""
    weights = [REALISTIC_HCMC_PEAK_PRIOR[ts] for ts in ["06:30", "07:00", "07:30", "08:00", "08:30", "09:00", "09:30"]]
    return np.array(weights, dtype=float) * base_rate_vps


def compute_regularized_loss(
    v_sim: np.ndarray,
    v_obs: np.ndarray,
    weights: np.ndarray,
    lambda_vec: np.ndarray,
    lambda_prior: np.ndarray,
    gamma_smooth: float = 2.0,
    gamma_prior: float = 1.5,
    w_pen: float = 0.0,
    bpr_penalty: float = 0.0,
) -> Tuple[float, Dict[str, float]]:
    r"""
    Đánh giá hàm mục tiêu điều chuẩn:
      \mathcal{L}(\boldsymbol{\lambda}) =
          \text{RMSE}_w(\mathbf{V}_{\text{sim}}, \mathbf{V}_{\text{obs}})
          + \gamma_{\text{smooth}} \|\Delta^2 \boldsymbol{\lambda}\|^2
          + \gamma_{\text{prior}} \|\boldsymbol{\lambda} - \boldsymbol{\lambda}_{\text{prior}}\|^2
          + w_{\text{pen}} \cdot \mathcal{P}_{\text{BPR}}^{\text{norm}}(\boldsymbol{\lambda})
    """
    diff_sq = (v_sim - v_obs) ** 2
    w_sum = np.sum(weights)
    if w_sum > 0:
        rmse_w = float(np.sqrt(np.sum(weights * diff_sq) / w_sum))
    else:
        rmse_w = float(np.sqrt(np.mean(diff_sq)))

    # Điều chuẩn trơn vi phân bậc hai: \sum (\lambda_{k+2} - 2\lambda_{k+1} + \lambda_k)^2
    K = len(lambda_vec)
    if K >= 3:
        laplacian_diff = lambda_vec[2:] - 2.0 * lambda_vec[1:-1] + lambda_vec[:-2]
        smooth_term = float(np.sum(laplacian_diff ** 2))
    else:
        smooth_term = 0.0

    # Khóa hình dáng tiên nghiệm HOUTRANS
    prior_diff = lambda_vec - lambda_prior
    prior_term = float(np.sum(prior_diff ** 2))

    total_loss = float(
        rmse_w
        + gamma_smooth * smooth_term
        + gamma_prior * prior_term
        + w_pen * bpr_penalty
    )

    details = {
        "rmse_w": round(rmse_w, 3),
        "smooth_term": round(smooth_term, 4),
        "prior_term": round(prior_term, 4),
        "bpr_penalty": round(bpr_penalty, 6),
        "total_loss": round(total_loss, 4),
    }
    return total_loss, details


class CmaesCalibrator:
    """Bộ điều phối tối ưu hóa CMA-ES đa tiến trình."""

    def __init__(
        self,
        target_date: str = "2026-10-15",
        n_workers: int = 3,
        pop_size: int = 9,
        max_generations: int = 10,
        gamma_smooth: float = 2.0,
        gamma_prior: float = 0.8,
        w_pen: float = 0.0,
        base_rate_prior: float = 1.0,
        use_crn: bool = False,
        crn_seeds: Tuple[int, ...] = (42, 100),
        storage_url: Optional[str] = None,
        study_name: str = "cmaes_demand_calibration",
    ):
        self.target_date = target_date
        self.n_workers = n_workers
        self.pop_size = pop_size
        self.max_generations = max_generations
        self.total_trials = pop_size * max_generations
        self.gamma_smooth = gamma_smooth
        self.gamma_prior = gamma_prior
        self.w_pen = w_pen
        self.use_crn = use_crn
        self.crn_seeds = crn_seeds
        self.study_name = study_name

        if storage_url is None:
            db_path = PROCESSED_DIR / "cmaes_study.db"
            self.storage_url = f"sqlite:///{db_path}"
        else:
            self.storage_url = storage_url

        # Nạp dữ liệu mục tiêu
        self.targets = load_calibration_targets_npz()
        self.ordered_points = self.targets["point_ids"]
        self.v0_vector = self.targets["v0_free_flow"]
        self.lambda_prior = build_realistic_peak_prior_7slices(base_rate_vps=base_rate_prior)

        # Trích xuất V_obs và W theo ngày hoặc trung vị lịch sử
        if target_date == "median" or target_date == "all":
            self.v_obs = self.targets["v_historical_median"]
            # Tạo ma trận trọng số đồng đều trên các lát cắt
            self.weights = np.ones_like(self.v_obs) / float(len(self.ordered_points))
        else:
            if target_date not in self.targets["v_obs_by_date"]:
                raise KeyError(f"Ngày {target_date} không có trong tập mục tiêu: {self.targets['dates']}")
            self.v_obs = self.targets["v_obs_by_date"][target_date]
            self.weights = self.targets["weights_by_date"][target_date]

        # Khởi tạo Checkpoint Warm-up
        ckpt_dir = SCENARIOS_DIR / "q1_calibrated_morning"
        self.checkpoint_file = ckpt_dir / "checkpoint_warmup_0630_v04.xml"
        ensure_warmup_checkpoint(
            self.checkpoint_file,
            warmup_duration=1800.0,
            step_length=0.4,
            lateral_resolution=0.40,
            force_recreate=False
        )

    def objective(self, trial: optuna.Trial) -> float:
        """Hàm đánh giá cho 1 cá thể trong Optuna."""
        # Gợi ý vector 7 chiều trong khoảng thực tế cao điểm [0.50, 4.00]
        lambda_candidate = np.zeros(7, dtype=float)
        for i, ts in enumerate(["0630", "0700", "0730", "0800", "0830", "0900", "0930"]):
            lambda_candidate[i] = trial.suggest_float(f"lambda_{ts}", 0.50, 4.00)

        # Chạy mô phỏng vi mô SUMO ngầm
        trial_tag = f"trial_{trial.number}"
        if self.use_crn:
            v_sim, telemetry = evaluate_candidate_crn(
                lambda_vec=lambda_candidate,
                ordered_points=self.ordered_points,
                v0_vector=self.v0_vector,
                checkpoint_file=self.checkpoint_file,
                crn_seeds=self.crn_seeds,
                tag=trial_tag
            )
        else:
            v_sim, telemetry = evaluate_candidate(
                lambda_vec=lambda_candidate,
                ordered_points=self.ordered_points,
                v0_vector=self.v0_vector,
                checkpoint_file=self.checkpoint_file,
                seed=42 + (trial.number % 7),
                tag=trial_tag
            )

        # Tính hàm mục tiêu điều chuẩn
        loss, details = compute_regularized_loss(
            v_sim=v_sim,
            v_obs=self.v_obs,
            weights=self.weights,
            lambda_vec=lambda_candidate,
            lambda_prior=self.lambda_prior,
            gamma_smooth=self.gamma_smooth,
            gamma_prior=self.gamma_prior,
            w_pen=self.w_pen,
        )

        # Lưu telemetry vào attributes của trial
        for k, v in details.items():
            trial.set_user_attr(k, v)
        for k, v in telemetry.items():
            trial.set_user_attr(k, v)

        return loss

    def run(self) -> Dict[str, Any]:
        """Thực thi tối ưu hóa song song bằng CMA-ES."""
        print("=" * 70)
        print(f"[*] BẮT ĐẦU TỐI ƯU HÓA CMA-ES: Mục tiêu = {self.target_date}")
        print(f"    • Kích thước quần thể: {self.pop_size} cá thể/thế hệ")
        print(f"    • Số thế hệ tối đa:     {self.max_generations} thế hệ ({self.total_trials} trials)")
        print(f"    • Số tiến trình song song: {self.n_workers} workers")
        print(f"    • Cơ sở dữ liệu SQLite:  {self.storage_url}")
        print("=" * 70)

        sampler = CmaEsSampler(
            seed=42,
            n_startup_trials=self.pop_size,
        )

        study = optuna.create_study(
            study_name=self.study_name,
            storage=self.storage_url,
            sampler=sampler,
            direction="minimize",
            load_if_exists=True,
        )

        completed_trials = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])
        remaining_trials = max(0, self.total_trials - completed_trials)

        if remaining_trials <= 0:
            print(f"[*] Nghiên cứu đã hoàn tất đủ {completed_trials}/{self.total_trials} trials từ trước!")
        else:
            print(f"[*] Đã hoàn thành trước đó {completed_trials}/{self.total_trials} trials. Tự động chạy tiếp {remaining_trials} trials còn lại...")
            # Chạy tối ưu hóa song song
            study.optimize(
                self.objective,
                n_trials=remaining_trials,
                n_jobs=self.n_workers,
                show_progress_bar=True,
            )

        best_trial = study.best_trial
        best_lambda = np.array([best_trial.params[f"lambda_{ts}"] for ts in ["0630", "0700", "0730", "0800", "0830", "0900", "0930"]])

        print("\n" + "=" * 70)
        print("[+] TỐI ƯU HÓA CMA-ES HOÀN TẤT THÀNH CÔNG!")
        print(f"    • Best Trial #{best_trial.number}: Loss = {best_trial.value:.4f}")
        print(f"    • Vector Lambda tối ưu:\n      {np.round(best_lambda, 3).tolist()}")
        print("=" * 70)

        # Xuất kết quả
        self.save_results(study, best_lambda)

        return {
            "best_loss": float(best_trial.value),
            "best_lambda": best_lambda.tolist(),
            "best_params": best_trial.params,
            "best_attrs": best_trial.user_attrs,
            "num_trials": len(study.trials),
        }

    def save_results(self, study: optuna.Study, best_lambda: np.ndarray) -> None:
        """Lưu trữ kết quả tối ưu, bảng lịch sử và biểu đồ hội tụ."""
        # 1. Tệp JSON lưu nghiệm tối ưu
        out_json = PROCESSED_DIR / "cmaes_best_params.json"
        best_info = {
            "target_date": self.target_date,
            "best_value": round(float(study.best_value), 4),
            "best_lambda_vps": [round(float(x), 4) for x in best_lambda],
            "best_params": study.best_trial.params,
            "best_user_attrs": study.best_trial.user_attrs,
            "total_trials": len(study.trials),
        }
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(best_info, f, ensure_ascii=False, indent=2)
        print(f"[+] Đã lưu nghiệm tốt nhất vào: {out_json.name}")

        # 2. Xuất bảng lịch sử Trials
        history_csv = PROCESSED_DIR / "cmaes_trial_history.csv"
        df_hist = study.trials_dataframe()
        df_hist.to_csv(history_csv, index=False, encoding="utf-8")
        print(f"[+] Đã xuất lịch sử tối ưu vào: {history_csv.name}")

        # 3. Vẽ biểu đồ hội tụ
        fig_png = PROCESSED_DIR / "cmaes_convergence.png"
        try:
            trials_values = [t.value for t in study.trials if t.value is not None]
            best_so_far = np.minimum.accumulate(trials_values)

            fig, ax = plt.subplots(figsize=(8, 5))
            ax.plot(trials_values, "o-", alpha=0.4, color="gray", label="Trial Loss")
            ax.plot(best_so_far, "r-", linewidth=2.5, label="Best Loss So Far")
            ax.set_xlabel("Trial Number", fontsize=11)
            ax.set_ylabel("Loss L(lambda)", fontsize=11)
            ax.set_title(f"CMA-ES Demand Optimization Convergence ({self.target_date})", fontsize=12, fontweight="bold")
            ax.grid(True, linestyle="--", alpha=0.6)
            ax.legend(frameon=True)
            fig.tight_layout()
            fig.savefig(fig_png, dpi=200)
            plt.close(fig)
            print(f"[+] Đã xuất biểu đồ hội tụ vào: {fig_png.name}")
        except Exception as e:
            print(f"[!] Warning khi vẽ biểu đồ hội tụ: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Tối ưu hóa CMA-ES Đa tiến trình")
    parser.add_argument("--date", type=str, default="2026-10-15", help="Ngày hiệu chuẩn (hoặc 'median')")
    parser.add_argument("--workers", type=int, default=3, help="Số luồng worker song song (mặc định: 3)")
    parser.add_argument("--generations", type=int, default=10, help="Số thế hệ tối đa")
    parser.add_argument("--pop-size", type=int, default=9, help="Kích thước quần thể mỗi thế hệ")
    parser.add_argument("--study-name", type=str, default="cmaes_realistic_prior_pilot", help="Tên nghiên cứu Optuna Study")
    parser.add_argument("--clean", action="store_true", help="Xóa study cũ cùng tên để chạy lại từ đầu")
    parser.add_argument("--crn", action="store_true", help="Kích hoạt kỹ thuật CRN trên 2 seeds")
    args = parser.parse_args()

    # Nếu người dùng yêu cầu --clean, xóa study cũ khỏi SQLite
    if args.clean:
        db_path = PROCESSED_DIR / "cmaes_study.db"
        if db_path.exists():
            storage = f"sqlite:///{db_path}"
            try:
                optuna.delete_study(study_name=args.study_name, storage=storage)
                print(f"[*] Đã xóa sạch study cũ '{args.study_name}' để bắt đầu tối ưu mới hoàn toàn.")
            except Exception:
                pass

    calibrator = CmaesCalibrator(
        target_date=args.date,
        n_workers=args.workers,
        pop_size=args.pop_size,
        max_generations=args.generations,
        study_name=args.study_name,
        use_crn=args.crn,
    )
    calibrator.run()
