"""
calibrate_bpr_optuna.py
Tự động hiệu chuẩn hai tham số BPR (alpha, beta) bằng Bayesian Optimization (Optuna)
dựa trên vòng lặp phản hồi mô phỏng vi mô (Simulation-in-the-loop):

Mục tiêu (Objective):
    Tìm (alpha*, beta*) sao cho dòng xe mô phỏng trong SUMO tái hiện chính xác nhất
    vận tốc thực tế đo được từ dữ liệu TomTom:
    Loss = RMSE(v_SUMO, v_TomTom) -> MIN

Quy trình mỗi Trial:
    1. Optuna đề xuất (alpha, beta).
    2. Chuyển đổi dữ liệu TomTom thành edge_counts.xml tương ứng.
    3. Hiệu chuẩn lộ trình vi mô bằng routeSampler.py.
    4. Chạy SUMO headless và đo vận tốc trung bình trên các cạnh (edgeData).
    5. So khớp v_SUMO với v_TomTom và tính RMSE.
"""

import os
import sys
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo import config và generate_sumo_counts từ 04_sumo_bridge
_SCRIPT_DIR = Path(__file__).resolve().parent
_MODULE_ROOT = _SCRIPT_DIR.parent
_SUMO_BRIDGE_DIR = _MODULE_ROOT / "04_sumo_bridge"
for p in [_SCRIPT_DIR, _MODULE_ROOT, _SUMO_BRIDGE_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler

from config import (
    BASE_DIR,
    PROCESSED_DATA_DIR,
    NETWORK_XML_PATH
)
from generate_sumo_counts import SumoNetworkMatcher, generate_sumo_counts

# Thư mục tạm cho các trial
TEMP_DIR = BASE_DIR / "temp_optuna"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

SUMO_HOME = os.getenv("SUMO_HOME", r"C:\Program Files (x86)\Eclipse\Sumo")
ROUTESAMPLER_PY = Path(SUMO_HOME) / "tools" / "routeSampler.py"


def parse_sumo_edge_speeds(edgedata_xml: Path) -> Dict[str, float]:
    """Đọc vận tốc trung bình (km/h) của từng cạnh từ file edgedata-output của SUMO."""
    if not edgedata_xml.exists() or edgedata_xml.stat().st_size == 0:
        return {}
    speeds = {}
    try:
        tree = ET.parse(edgedata_xml)
        root = tree.getroot()
        for interval in root.findall("interval"):
            for edge in interval.findall("edge"):
                eid = edge.get("id")
                spd_str = edge.get("speed")
                if eid and spd_str:
                    spd_ms = float(spd_str)
                    speeds[eid] = spd_ms * 3.6  # m/s -> km/h
    except Exception as e:
        print(f"[!] Loi parse XML edgedata: {e}")
    return speeds


def get_ground_truth_speeds(df: pd.DataFrame, matcher: SumoNetworkMatcher) -> Dict[str, float]:
    """Lấy vận tốc thực tế trung bình (km/h) từ dữ liệu TomTom cho các cạnh SUMO."""
    grouped = df.groupby("point_id").agg({
        "lat": "first",
        "lon": "first",
        "current_speed_kmh": "mean"
    }).reset_index()

    edge_speeds = {}
    for _, row in grouped.iterrows():
        p_id = row["point_id"]
        lat = float(row["lat"])
        lon = float(row["lon"])
        speed = float(row["current_speed_kmh"])

        res = matcher.find_best_matching_edge(lat, lon, p_id)
        if res:
            edge_id, _ = res
            edge_speeds[edge_id] = speed
    return edge_speeds


def run_calibration_study(
    input_csv: Path,
    candidates_rou: Path,
    n_trials: int = 30,
    eval_duration: int = 600,
    start_time: str = None,
    end_time: str = None
):
    print("==================================================")
    print("[*] KHOI DONG BAYESIAN OPTIMIZATION HIỆU CHUẨN BPR (ALPHA, BETA)")
    print(f"[*] Input Data: {input_csv}")
    print(f"[*] So luong Trials: {n_trials}")
    print(f"[*] Thoi luong mo phong moi trial: {eval_duration} giay")
    if start_time and end_time:
        print(f"[*] Khung gio danh gia: {start_time} -> {end_time}")
    print("==================================================")

    if not input_csv.exists():
        print(f"[!] Khong tim thay file: {input_csv}")
        return None

    if not candidates_rou.exists():
        print(f"[!] Khong tim thay file candidate routes: {candidates_rou}")
        return None

    # 1. Đọc dữ liệu và trích xuất Vận tốc thực tế (Ground Truth)
    df = pd.read_csv(input_csv)
    df["dt"] = pd.to_datetime(df["timestamp"])
    if start_time:
        st = pd.to_datetime(start_time).time()
        df = df[df["dt"].dt.time >= st]
    if end_time:
        et = pd.to_datetime(end_time).time()
        df = df[df["dt"].dt.time <= et]

    matcher = SumoNetworkMatcher(NETWORK_XML_PATH)
    ground_truth_speeds = get_ground_truth_speeds(df, matcher)
    print(f"[*] Da trich xuat duoc van toc thuc te tren {len(ground_truth_speeds)} canh do.")

    # 2. Định nghĩa hàm mục tiêu cho Optuna
    def objective(trial: optuna.Trial) -> float:
        # Gợi ý tham số alpha và beta liên tục (không dùng step để TPE hội tụ tự nhiên)
        alpha = trial.suggest_float("alpha", 0.10, 1.20)
        beta = trial.suggest_float("beta", 1.00, 4.50)

        trial_id = trial.number
        trial_counts_xml = TEMP_DIR / f"counts_t{trial_id}.xml"
        trial_calib_rou = TEMP_DIR / f"calib_t{trial_id}.rou.xml"
        trial_speed_xml = TEMP_DIR / f"speed_t{trial_id}.xml"

        # Bước 1: Sinh file demand edge_counts.xml với (alpha, beta) này
        generate_sumo_counts(
            history_csv=input_csv,
            network_xml=NETWORK_XML_PATH,
            output_xml=trial_counts_xml,
            start_time=start_time,
            end_time=end_time,
            alpha=alpha,
            beta=beta
        )

        # Bước 2: Hiệu chuẩn lộ trình bằng routeSampler.py
        # Sử dụng python từ môi trường hiện tại
        py_exe = sys.executable
        cmd_sampler = [
            py_exe, str(ROUTESAMPLER_PY),
            "-r", str(candidates_rou),
            "-d", str(trial_counts_xml),
            "-o", str(trial_calib_rou),
            "--attributes", 'type="hcmc_mixed"',
            "--write-flows", "number",
            "--optimize", "full"
        ]
        res_sample = subprocess.run(cmd_sampler, capture_output=True, text=True)
        if res_sample.returncode != 0:
            print(f"[!] routeSampler error tai trial {trial_id}: {res_sample.stderr}")
            return 999.0

        # Bước 3: Chạy mô phỏng SUMO headless trong eval_duration
        cmd_sumo = [
            "sumo",
            "-n", str(NETWORK_XML_PATH),
            "-r", str(trial_calib_rou),
            "-a", str(BASE_DIR.parent / "data" / "raw_data" / "vtypes.add.xml"),
            "--begin", "0",
            "--end", str(eval_duration),
            "--step-length", "1.0",
            "--lateral-resolution", "0.8",
            "--edgedata-output", str(trial_speed_xml),
            "--collision.action", "none",
            "--time-to-teleport", "120",
            "--no-warnings", "true",
            "--no-step-log", "true"
        ]
        res_sumo = subprocess.run(cmd_sumo, capture_output=True, text=True)
        if res_sumo.returncode != 0:
            print(f"[!] SUMO error tai trial {trial_id}: {res_sumo.stderr}")
            return 999.0

        # Bước 4: Parse kết quả vận tốc từ SUMO và so khớp với TomTom
        sim_speeds = parse_sumo_edge_speeds(trial_speed_xml)

        common_edges = set(ground_truth_speeds.keys()).intersection(sim_speeds.keys())
        if len(common_edges) < 10:
            print(f"[!] Canh hop le qua it ({len(common_edges)}), phat loss cao.")
            return 50.0

        y_real = [ground_truth_speeds[e] for e in common_edges]
        y_sim = [sim_speeds[e] for e in common_edges]

        rmse = float(np.sqrt(np.mean((np.array(y_sim) - np.array(y_real)) ** 2)))
        mae = float(np.mean(np.abs(np.array(y_sim) - np.array(y_real))))

        trial.set_user_attr("mae", round(mae, 2))
        trial.set_user_attr("matched_edges", len(common_edges))

        # Dọn dẹp file tạm của trial
        for p in [trial_counts_xml, trial_calib_rou, trial_speed_xml]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

        print(f"--> [Trial {trial_id:02d}] alpha={alpha:.3f}, beta={beta:.3f} | RMSE: {rmse:.2f} km/h | MAE: {mae:.2f} km/h")
        return rmse

    # 3. Chạy quá trình tối ưu
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = TPESampler(seed=42)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials)

    print("\n==================================================")
    print("[OK] HOAN TAT QUA TRINH BAYESIAN OPTIMIZATION!")
    print(f"[*] Ket qua toi uu nhat:")
    print(f"    - Alpha*: {study.best_params['alpha']:.3f}")
    print(f"    - Beta*:  {study.best_params['beta']:.3f}")
    print(f"    - RMSE toi thieu: {study.best_value:.2f} km/h")
    print("==================================================")

    # 4. Xuất lịch sử ra CSV và JSON
    trials_df = study.trials_dataframe()
    out_csv = PROCESSED_DATA_DIR / "bpr_optuna_history.csv"
    trials_df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    best_res = {
        "best_alpha": study.best_params["alpha"],
        "best_beta": study.best_params["beta"],
        "best_rmse_kmh": study.best_value,
        "n_trials": n_trials,
        "eval_duration_s": eval_duration,
        "input_dataset": str(input_csv.name)
    }
    out_json = PROCESSED_DATA_DIR / "bpr_best_params.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(best_res, f, indent=2, ensure_ascii=False)

    print(f"[*] Da luu lich su trials vao: {out_csv}")
    print(f"[*] Da luu tham so toi uu vao: {out_json}")
    return study.best_params


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bayesian Optimization for BPR Parameters (alpha, beta)")
    parser.add_argument("--input", "-i", type=str, default=str(PROCESSED_DATA_DIR / "macro_traffic_dense_1min.csv"),
                        help="File CSV du lieu cào")
    parser.add_argument("--trials", "-t", type=int, default=20,
                        help="So luong trials (mac dinh: 20)")
    parser.add_argument("--duration", "-d", type=int, default=600,
                        help="Thoi luong mo phong danh gia moi trial (giay, mac dinh: 600s = 10 phut)")
    parser.add_argument("--start-time", "-s", type=str, default="17:00",
                        help="Gio bat dau khung gio danh gia (mac dinh: 17:00)")
    parser.add_argument("--end-time", "-e", type=str, default="18:00",
                        help="Gio ket thuc khung gio danh gia (mac dinh: 18:00)")

    args = parser.parse_args()

    candidates_file = BASE_DIR.parent / "candidate_routes.rou.xml"
    run_calibration_study(
        input_csv=Path(args.input),
        candidates_rou=candidates_file,
        n_trials=args.trials,
        eval_duration=args.duration,
        start_time=args.start_time,
        end_time=args.end_time
    )
