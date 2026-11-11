r"""
freeze_scenario.py
=============================================================================
KHÓA KỊCH BẢN CHUẨN HÓA & LƯU SNAPSHOT TRẠNG THÁI KHỞI ĐỘNG (WARM-UP 07:00)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận:
- SD_EVALUATION.md (Mục 1.4 & Mục IX)
- ROADMAP_50DAYS.md (Nhiệm vụ 1.5)

Nội dung bàn giao sang Chặng 2 (MARL Environment Adapter):
1. Xuất tệp lộ trình đóng băng: calibrated_morning_peak.rou.xml
   (Tích hợp mô hình Sublane 85/12/3, nạp ngoại vi fringe-factor 8.0, nhu cầu lambda*).
2. Lưu snapshot trạng thái giao thông lúc 07:00: checkpoint_warmup_0700.xml
   (Bỏ qua 3.600s khởi động, đưa môi trường RL vào ngay cao điểm sáng 07:00).
3. Kiểm thử tự động khả năng khôi phục với --load-state trong SUMO.
4. Xuất SCENARIO_MANIFEST.json ghi nhận đầy đủ checksum và thông số môi trường.
=============================================================================
"""

import os
import sys
import json
import shutil
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

import numpy as np

# Hạ mức ưu tiên tiến trình
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
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw_data"
PROCESSED_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "data" / "processed"
SCENARIOS_DIR = PROJECT_ROOT / "sumo_scenarios"
TARGET_DIR = SCENARIOS_DIR / "q1_calibrated_morning"

DEFAULT_NET_FILE = RAW_DATA_DIR / "q1_map.net.xml"
DEFAULT_VTYPES_FILE = RAW_DATA_DIR / "vtypes.add.xml"

# Import hàm sinh routes từ sumo_headless_runner
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
from sumo_headless_runner import generate_multislice_routes, get_sumo_binary


def compute_file_sha256(filepath: Path) -> str:
    """Tính mã băm SHA-256 để niêm phong tính toàn vẹn của tệp."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def freeze_calibrated_scenario(
    best_lambda: Optional[np.ndarray] = None,
    net_file: Path = DEFAULT_NET_FILE,
    vtypes_file: Path = DEFAULT_VTYPES_FILE,
    warmup_rate_vps: float = 0.35,
    seed: int = 42
) -> Dict[str, Any]:
    r"""
    Thực hiện quy trình đóng băng kịch bản cao điểm sáng và tạo snapshot 07:00.
    """
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Nếu không truyền lambda, nạp từ cmaes_best_params.json hoặc prior
    if best_lambda is None:
        best_json = PROCESSED_DIR / "cmaes_best_params.json"
        if best_json.exists():
            with open(best_json, "r", encoding="utf-8") as f:
                info = json.load(f)
                best_lambda = np.array(info["best_lambda_vps"], dtype=float)
                print(f"[*] Nạp vector lambda* từ {best_json.name}: {best_lambda.tolist()}")
        else:
            # Fallback: dùng vector tiên nghiệm HOUTRANS chuẩn
            best_lambda = np.array([0.85, 1.25, 1.50, 1.35, 1.10, 0.90, 0.85], dtype=float)
            print(f"[!] Không tìm thấy best_params, sử dụng HOUTRANS baseline: {best_lambda.tolist()}")

    # 2. Xây dựng vector toàn khung giờ từ 06:00 đến 10:00 (8 lát cắt x 1800s)
    # Lát 0 (06:00 - 06:30): warmup_rate_vps
    # Lát 1..7 (06:30 - 10:00): best_lambda
    full_lambda = np.concatenate([[warmup_rate_vps], best_lambda])
    output_rou_file = TARGET_DIR / "calibrated_morning_peak.rou.xml"

    print(f"[*] Sinh tệp lộ trình đóng băng: {output_rou_file.name} (8 lát cắt, tổng 14.400s)...")
    generate_multislice_routes(
        lambda_vec=full_lambda,
        output_rou_file=output_rou_file,
        net_file=net_file,
        vtypes_file=vtypes_file,
        slice_duration=1800.0,
        begin_time=0.0,
        seed=seed,
        work_dir=TARGET_DIR
    )

    # 3. Tạo tệp cấu hình mô phỏng chuẩn: simulation.sumocfg
    sumocfg_file = TARGET_DIR / "simulation.sumocfg"
    sumocfg_content = f"""<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <!-- Mạng lưới giao thông chuẩn Quận 1 & Quận 3 (34 nút đèn tín hiệu) -->
        <net-file value="{os.path.relpath(net_file, TARGET_DIR).replace('\\', '/')}"/>
        <!-- Lộ trình nhu cầu cao điểm sáng đã hiệu chuẩn qua CMA-ES -->
        <route-files value="{output_rou_file.name}"/>
    </input>

    <time>
        <begin value="0"/>
        <end value="14400"/>
        <step-length value="0.2"/>
    </time>

    <processing>
        <!-- Kích hoạt Sublane Model: chia làn phụ 0.25m cho xe máy luồn lách tự do -->
        <lateral-resolution value="0.25"/>
        <collision.action value="warn"/>
        <time-to-teleport value="120"/>
    </processing>

    <report>
        <verbose value="false"/>
        <no-step-log value="true"/>
    </report>
</configuration>
"""
    with open(sumocfg_file, "w", encoding="utf-8") as f:
        f.write(sumocfg_content)
    print(f"[+] Đã tạo tệp cấu hình mô phỏng: {sumocfg_file.name}")

    # 4. Chạy mô phỏng giai đoạn khởi động 06:00 - 07:00 (3.600s) và lưu checkpoint 07:00
    checkpoint_file = TARGET_DIR / "checkpoint_warmup_0700.xml"
    sumo_bin = get_sumo_binary()
    if not checkpoint_file.exists():
        print(f"[*] Chạy mô phỏng khởi động (06:00 - 07:00) để lưu {checkpoint_file.name}...")
        cmd_save = [
            sumo_bin,
            "-c", str(sumocfg_file),
            "--begin", "0",
            "--end", "3601",
            "--save-state.times", "3600",
            "--save-state.files", str(checkpoint_file),
            "--no-step-log", "true",
            "--seed", str(seed),
        ]
        res_save = subprocess.run(cmd_save, capture_output=True, text=True)
        if res_save.returncode != 0:
            raise RuntimeError(f"Lỗi khi lưu checkpoint 07:00:\n{res_save.stderr}")

    if not checkpoint_file.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp checkpoint: {checkpoint_file}")

    ckpt_size_kb = checkpoint_file.stat().st_size / 1024.0
    print(f"[+] Checkpoint 07:00 sẵn sàng: {checkpoint_file.name} ({ckpt_size_kb:.1f} KB)")

    # 5. Kiểm thử nạp lại checkpoint với --load-state (Smoke-test khôi phục)
    print(f"[*] Kiểm thử khôi phục trạng thái (Smoke-test) tại t=3600...")
    cmd_load = [
        sumo_bin,
        "-c", str(sumocfg_file),
        "--load-state", str(checkpoint_file),
        "--begin", "3600",
        "--end", "3620",
        "--no-step-log", "true",
    ]
    res_load = subprocess.run(cmd_load, capture_output=True, text=True)
    if res_load.returncode != 0:
        raise RuntimeError(f"Lỗi khi nạp lại checkpoint 07:00:\n{res_load.stderr}")
    print(f"[+] Smoke-test hoàn tất: Checkpoint 07:00 nạp lại hoàn hảo không lỗi!")

    # 6. Xuất SCENARIO_MANIFEST.json
    manifest_file = TARGET_DIR / "SCENARIO_MANIFEST.json"
    manifest = {
        "scenario_name": "q1_calibrated_morning_peak",
        "description": "Kịch bản giao thông cao điểm sáng Quận 1 & 3 hiệu chuẩn qua CMA-ES",
        "created_at": datetime.now().isoformat(),
        "time_window": "06:00 - 10:00 (14,400s)",
        "warmup_window": "06:00 - 07:00 (3,600s)",
        "evaluation_window": "07:00 - 09:30 (9,000s)",
        "drain_window": "09:30 - 10:00 (1,800s)",
        "sublane_resolution_m": 0.25,
        "step_length_s": 0.20,
        "yellow_time_s": 3.0,
        "modal_split": "85% Motorcycle, 12% Car, 3% Bus",
        "calibrated_lambda_vector": [round(float(x), 4) for x in best_lambda],
        "files": {
            "routes_file": {
                "name": output_rou_file.name,
                "sha256": compute_file_sha256(output_rou_file),
                "size_mb": round(output_rou_file.stat().st_size / (1024 * 1024), 2),
            },
            "checkpoint_0700": {
                "name": checkpoint_file.name,
                "sha256": compute_file_sha256(checkpoint_file),
                "size_kb": round(ckpt_size_kb, 1),
            },
            "config_file": {
                "name": sumocfg_file.name,
                "sha256": compute_file_sha256(sumocfg_file),
            }
        }
    }
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[+] Đã niêm phong kịch bản tại: {manifest_file.name}")

    return manifest


if __name__ == "__main__":
    print("=" * 70)
    print("[*] THỰC THI KHÓA KỊCH BẢN: freeze_scenario.py")
    print("=" * 70)
    res = freeze_calibrated_scenario()
    print("\n" + "=" * 70)
    print("[OK] KỊCH BẢN ĐÃ ĐƯỢC ĐÓNG BĂNG VÀ SẴN SÀNG BÀN GIAO SANG CHẶNG 2!")
    print("=" * 70)
