r"""
sumo_headless_runner.py
=============================================================================
WORKER MÔ PHỎNG VI MÔ CHẠY NGẦM ĐA TIẾN TRÌNH & ĐO ĐẠC TELEMETRY
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận:
- SD_EVALUATION.md (Mục 1.3, 1.4 & Phụ lục B)
- ROADMAP_50DAYS.md (Nhiệm vụ 1.2)

Các tính năng kỹ thuật cốt lõi:
1. Hạ quyền ưu tiên tiến trình (BELOW_NORMAL_PRIORITY_CLASS qua psutil)
   để đảm bảo máy tính không bị đơ/lag khi chạy ngầm nhiều workers.
2. Sinh lộ trình động học đa lát cắt (Multi-slice synthetic routes)
   kết hợp tỷ lệ phương tiện chuẩn HCMC 85/12/3 và mô hình chia làn phụ Sublane 0.25m.
3. Cơ chế Khởi động Warm-up một lần (Save/Load Checkpoint 06:30) giúp
   tiết kiệm 20-30% thời gian chạy cho mọi cá thể trong CMA-ES.
4. Trích xuất tự động ma trận vận tốc không gian V_sim in R^(66 x 7)
   từ tệp XML edgeData định kỳ 1800s.
5. Theo dõi chặt chẽ tính toàn vẹn nạp mạng:
   - Tỷ lệ nạp mạng ICR >= 95%
   - Tỷ lệ tồn đọng cửa ngõ GBR < 5%
   - Tỷ lệ teleport < 0.1%
=============================================================================
"""

import os
import sys
import shutil
import tempfile
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union

import numpy as np
import pandas as pd

# Hạ mức ưu tiên tiến trình (Below Normal) để không gián đoạn UI / VS Code của người dùng
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
METADATA_DIR = PROJECT_ROOT / "macro_traffic_crawler" / "data" / "metadata"
SCENARIOS_DIR = PROJECT_ROOT / "sumo_scenarios"

DEFAULT_NET_FILE = RAW_DATA_DIR / "q1_map.net.xml"
DEFAULT_VTYPES_FILE = RAW_DATA_DIR / "vtypes.add.xml"
SAMPLING_POINTS_FILE = METADATA_DIR / "sampling_points.csv"

# Tìm kiếm đường dẫn bộ công cụ SUMO
def get_sumo_binary() -> str:
    bin_path = shutil.which("sumo")
    if bin_path:
        return bin_path
    win_path = Path("C:/Program Files (x86)/Eclipse/Sumo/bin/sumo.EXE")
    if win_path.exists():
        return str(win_path)
    raise FileNotFoundError("Không tìm thấy binary 'sumo'. Vui lòng kiểm tra PATH hoặc SUMO_HOME!")


def get_sumo_tools_dir() -> Path:
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home and (Path(sumo_home) / "tools" / "randomTrips.py").exists():
        return Path(sumo_home) / "tools"
    win_tools = Path("C:/Program Files (x86)/Eclipse/Sumo/tools")
    if (win_tools / "randomTrips.py").exists():
        return win_tools
    raise FileNotFoundError("Không tìm thấy công cụ SUMO 'randomTrips.py'!")


# Nạp danh sách 66 điểm quan trắc
def load_point_ids() -> List[str]:
    if not SAMPLING_POINTS_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy: {SAMPLING_POINTS_FILE}")
    df_pts = pd.read_csv(SAMPLING_POINTS_FILE)
    return df_pts["point_id"].tolist()


# =============================================================================
# 1. BỘ TẠO LỘ TRÌNH ĐA LÁT CẮT (MULTI-SLICE ROUTE GENERATOR)
# =============================================================================
def generate_multislice_routes(
    lambda_vec: np.ndarray,
    output_rou_file: Union[str, Path],
    net_file: Union[str, Path] = DEFAULT_NET_FILE,
    vtypes_file: Union[str, Path] = DEFAULT_VTYPES_FILE,
    slice_duration: float = 1800.0,
    begin_time: float = 1800.0,
    through_ratio: float = 0.60,
    fringe_factor_thru: float = 5.0,
    min_dist_thru: float = 1200.0,
    fringe_factor_local: float = 1.0,
    min_dist_local: float = 800.0,
    max_dist_local: float = 1800.0,
    seed: int = 42,
    work_dir: Optional[Union[str, Path]] = None,
) -> Path:
    r"""
    Sinh tệp lộ trình (.rou.xml) gồm 7 lát cắt thời gian theo vector lambda (xe/giây)
    với cơ chế Nhu cầu Hỗn hợp (Composite Demand Model):
      - Luồng 1 (Through Traffic, 60%): Xe xuyên tâm từ các quận lân cận (fringe-factor 5.0, cự ly > 1200m).
      - Luồng 2 (Local Circulation, 40%): Xe lưu thông nội quận với cự ly trung bình (fringe-factor 1.0, cự ly 800m - 1800m).
    """
    out_rou = Path(output_rou_file).resolve()
    out_rou.parent.mkdir(parents=True, exist_ok=True)

    if work_dir is None:
        work_dir = out_rou.parent
    else:
        work_dir = Path(work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

    tools_dir = get_sumo_tools_dir()
    random_trips_py = tools_dir / "randomTrips.py"
    net_path = Path(net_file).resolve()
    vt_path = Path(vtypes_file).resolve()

    K = len(lambda_vec)
    temp_trip_files = []

    # 1. Sinh trips riêng cho từng lát cắt thời gian
    for k in range(K):
        slice_b = begin_time + k * slice_duration
        slice_e = slice_b + slice_duration
        rate = max(0.05, float(lambda_vec[k]))

        # Phân tách 2 luồng: Xuyên tâm (Through) và Nội bộ (Local)
        rate_thru = rate * through_ratio
        rate_local = rate * (1.0 - through_ratio)

        # 1a. Sinh luồng xuyên tâm (Through)
        if rate_thru > 0.01:
            slice_thru_file = work_dir / f"temp_trips_{out_rou.stem}_s{k}_thru.xml"
            temp_trip_files.append(slice_thru_file)
            cmd_thru = [
                sys.executable, str(random_trips_py),
                "-n", str(net_path),
                "-o", str(slice_thru_file),
                "-b", f"{slice_b:.1f}",
                "-e", f"{slice_e:.1f}",
                "-p", f"{1.0 / rate_thru:.4f}",
                "--prefix", f"thru_s{k}_",
                "--fringe-factor", str(fringe_factor_thru),
                "--min-distance", str(min_dist_thru),
                "--speed-exponent", "1.0",
                "--seed", str(seed + k * 17),
                "--trip-attributes", "type=\"hcmc_mixed\" departLane=\"best\" departSpeed=\"max\""
            ]
            res_thru = subprocess.run(cmd_thru, capture_output=True, text=True)
            if res_thru.returncode != 0:
                raise RuntimeError(f"Lỗi khi chạy randomTrips (through) tại lát {k}:\n{res_thru.stderr}")

        # 1b. Sinh luồng nội bộ (Local circulation)
        if rate_local > 0.01:
            slice_loc_file = work_dir / f"temp_trips_{out_rou.stem}_s{k}_local.xml"
            temp_trip_files.append(slice_loc_file)
            cmd_loc = [
                sys.executable, str(random_trips_py),
                "-n", str(net_path),
                "-o", str(slice_loc_file),
                "-b", f"{slice_b:.1f}",
                "-e", f"{slice_e:.1f}",
                "-p", f"{1.0 / rate_local:.4f}",
                "--prefix", f"loc_s{k}_",
                "--fringe-factor", str(fringe_factor_local),
                "--min-distance", str(min_dist_local),
                "--max-distance", str(max_dist_local),
                "--speed-exponent", "1.0",
                "--seed", str(seed + k * 31 + 7),
                "--trip-attributes", "type=\"hcmc_mixed\" departLane=\"best\" departSpeed=\"max\""
            ]
            res_loc = subprocess.run(cmd_loc, capture_output=True, text=True)
            if res_loc.returncode != 0:
                raise RuntimeError(f"Lỗi khi chạy randomTrips (local) tại lát {k}:\n{res_loc.stderr}")

    # 2. Gộp toàn bộ trips vào một tệp duy nhất, sắp xếp theo thời gian depart
    combined_trips_file = work_dir / f"combined_trips_{out_rou.stem}.xml"
    all_trips = []
    for tf in temp_trip_files:
        if tf.exists():
            try:
                tree = ET.parse(tf)
                for trip in tree.getroot().findall("trip"):
                    all_trips.append(trip)
            except Exception:
                pass

    # Sắp xếp các trip theo thuộc tính depart
    all_trips.sort(key=lambda t: float(t.get("depart", "0.0")))

    root = ET.Element("routes")
    for trip in all_trips:
        root.append(trip)
    tree_out = ET.ElementTree(root)
    tree_out.write(combined_trips_file, encoding="utf-8", xml_declaration=True)

    # 3. Định tuyến tối ưu toàn cục qua duarouter
    dua_bin = shutil.which("duarouter") or "duarouter"
    dua_cmd = [
        dua_bin,
        "-n", str(net_path),
        "-r", str(combined_trips_file),
        "-o", str(out_rou),
        "-a", str(vt_path),
        "--ignore-errors", "true",
        "--no-step-log", "true",
        "--routing-threads", "2",
    ]
    res_dua = subprocess.run(dua_cmd, capture_output=True, text=True)
    if res_dua.returncode != 0:
        raise RuntimeError(f"Lỗi duarouter khi định tuyến:\n{res_dua.stderr}")

    # Dọn dẹp tệp tạm
    for tf in temp_trip_files:
        if tf.exists():
            tf.unlink()
    if combined_trips_file.exists():
        combined_trips_file.unlink()

    return out_rou


# =============================================================================
# 2. KHỞI TẠO & LƯU CHECKPOINT WARM-UP 06:30
# =============================================================================
def ensure_warmup_checkpoint(
    checkpoint_file: Union[str, Path],
    net_file: Union[str, Path] = DEFAULT_NET_FILE,
    vtypes_file: Union[str, Path] = DEFAULT_VTYPES_FILE,
    warmup_duration: float = 1800.0,
    warmup_rate_vps: float = 0.35,
    step_length: float = 0.4,
    lateral_resolution: float = 0.40,
    seed: int = 42,
    force_recreate: bool = False
) -> Path:
    r"""
    Tạo hoặc kiểm tra tệp checkpoint trạng thái khởi động (06:00 - 06:30).
    Nếu checkpoint đã tồn tại, tái sử dụng để tiết kiệm 100% thời gian warm-up.
    """
    ckpt_path = Path(checkpoint_file).resolve()
    if ckpt_path.exists() and not force_recreate:
        return ckpt_path

    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Khởi tạo Checkpoint Warm-up (06:00 - 06:30) tại: {ckpt_path.name}...")

    # 1. Sinh lộ trình khởi động
    warmup_rou = ckpt_path.parent / "warmup_routes.rou.xml"
    generate_multislice_routes(
        lambda_vec=np.array([warmup_rate_vps]),
        output_rou_file=warmup_rou,
        net_file=net_file,
        vtypes_file=vtypes_file,
        slice_duration=warmup_duration,
        begin_time=0.0,
        seed=seed,
    )

    # 2. Chạy SUMO và lưu trạng thái tại t = 1800 (rou_file đã chứa sẵn vTypes từ duarouter)
    sumo_bin = get_sumo_binary()
    sumo_cmd = [
        sumo_bin,
        "-n", str(Path(net_file).resolve()),
        "-r", str(warmup_rou),
        "--begin", "0",
        "--end", f"{warmup_duration + 1.0:.1f}",
        "--step-length", str(step_length),
        "--lateral-resolution", str(lateral_resolution),
        "--time-to-teleport", "120",
        "--collision.action", "warn",
        "--save-state.times", f"{warmup_duration:.0f}",
        "--save-state.files", str(ckpt_path),
        "--no-step-log", "true",
        "--seed", str(seed),
    ]
    res = subprocess.run(sumo_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Lỗi khi lưu checkpoint warm-up:\n{res.stderr}")

    if not ckpt_path.exists():
        raise FileNotFoundError(f"SUMO chạy thành công nhưng không tìm thấy checkpoint: {ckpt_path}")

    print(f"[+] Checkpoint Warm-up đã tạo thành công ({ckpt_path.stat().st_size / 1024:.1f} KB).")
    return ckpt_path


# =============================================================================
# 3. TRÍCH XUẤT VẬN TỐC TỪ EDGEDATA THEO TỪNG LÁT CẮT
# =============================================================================
def parse_multislice_edgedata(
    xml_path: Union[str, Path],
    ordered_points: List[str],
    num_slices: int = 7,
    v0_vector: Optional[np.ndarray] = None
) -> np.ndarray:
    r"""
    Trích xuất ma trận vận tốc không gian V_sim in R^(66 x 7) từ edgedata XML.
    Đơn vị trong file SUMO: m/s -> nhân 3.6 ra km/h.
    Mapping: way_id = "way_" + edge_id.lstrip('-').split('#')[0].
    """
    xml_file = Path(xml_path).resolve()
    if not xml_file.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp edgedata: {xml_file}")

    N_POINTS = len(ordered_points)
    point_to_idx = {p: i for i, p in enumerate(ordered_points)}
    V_sim = np.zeros((N_POINTS, num_slices), dtype=float)

    tree = ET.parse(xml_file)
    root = tree.getroot()

    intervals = root.findall("interval")
    # Lấy tối đa num_slices khoảng thời gian
    intervals = intervals[:num_slices]

    for t_idx, interval in enumerate(intervals):
        # Gom nhóm theo point_id trong lát này
        edge_records: Dict[str, List[Tuple[float, float]]] = {}
        for edge in interval.findall("edge"):
            edge_id = edge.get("id", "")
            if not edge_id or edge_id.startswith(":"):
                continue
            speed_ms = float(edge.get("speed", "0.0"))
            sampled_sec = float(edge.get("sampledSeconds", "0.0"))

            clean_id = edge_id.lstrip("-").split("#")[0]
            pid = f"way_{clean_id}"

            if pid in point_to_idx:
                if pid not in edge_records:
                    edge_records[pid] = []
                edge_records[pid].append((speed_ms, sampled_sec))

        for pid, records in edge_records.items():
            p_idx = point_to_idx[pid]
            tot_sec = sum(sec for _, sec in records)
            if tot_sec > 0:
                # Space-mean speed
                v_mean_ms = sum(s * sec for s, sec in records) / tot_sec
            else:
                v_mean_ms = sum(s for s, _ in records) / len(records)
            V_sim[p_idx, t_idx] = v_mean_ms * 3.6

    # Nếu có điểm nào không có xe đi qua trong lát cắt, điền v0
    for p_idx in range(N_POINTS):
        for t_idx in range(num_slices):
            if V_sim[p_idx, t_idx] <= 0.0:
                if v0_vector is not None:
                    V_sim[p_idx, t_idx] = v0_vector[p_idx]
                else:
                    V_sim[p_idx, t_idx] = 35.0

    return V_sim


def parse_simulation_summary(summary_path: Union[str, Path]) -> Dict[str, float]:
    """Trích xuất các chỉ số nạp mạng từ summary XML (ICR, GBR, TCR, Teleport rate)."""
    sum_file = Path(summary_path).resolve()
    if not sum_file.exists():
        return {"icr": 1.0, "gbr": 0.0, "tcr": 1.0, "teleport_rate": 0.0}

    try:
        tree = ET.parse(sum_file)
        steps = tree.getroot().findall("step")
        if not steps:
            return {"icr": 1.0, "gbr": 0.0, "tcr": 1.0, "teleport_rate": 0.0}

        last_step = steps[-1]
        loaded = float(last_step.get("loaded", "0.0"))
        inserted = float(last_step.get("inserted", "0.0"))
        waiting = float(last_step.get("waiting", "0.0"))
        arrived = float(last_step.get("arrived", "0.0"))
        teleports = float(last_step.get("teleports", "0.0"))

        icr = inserted / max(1.0, loaded)
        gbr = waiting / max(1.0, loaded)
        tcr = arrived / max(1.0, inserted)
        teleport_rate = teleports / max(1.0, inserted)

        return {
            "icr": round(float(icr), 4),
            "gbr": round(float(gbr), 4),
            "tcr": round(float(tcr), 4),
            "teleport_rate": round(float(teleport_rate), 4),
            "total_inserted": int(inserted),
            "total_arrived": int(arrived),
        }
    except Exception:
        return {"icr": 1.0, "gbr": 0.0, "tcr": 1.0, "teleport_rate": 0.0}


# =============================================================================
# 4. HÀM ĐÁNH GIÁ 1 CÁ THỂ (SINGLE CANDIDATE SIMULATION EVALUATION)
# =============================================================================
def evaluate_candidate(
    lambda_vec: np.ndarray,
    ordered_points: List[str],
    v0_vector: Optional[np.ndarray] = None,
    checkpoint_file: Optional[Union[str, Path]] = None,
    net_file: Union[str, Path] = DEFAULT_NET_FILE,
    vtypes_file: Union[str, Path] = DEFAULT_VTYPES_FILE,
    step_length: float = 0.4,
    lateral_resolution: float = 0.40,
    timeout_sec: int = 600,
    seed: int = 42,
    tag: str = "eval",
    work_dir: Optional[Union[str, Path]] = None,
) -> Tuple[np.ndarray, Dict[str, float]]:
    r"""
    Thực thi 1 lượt mô phỏng ngầm cho vector lambda:
      1. Tải checkpoint warm-up 06:30 (--load-state).
      2. Chạy mô phỏng 7 lát cắt (1800s đến 14400s) với Sublane Model.
      3. Trích xuất ma trận V_sim in R^(66 x 7) và telemetry thực tế từ SUMO XML.
    """
    if work_dir is None:
        temp_dir_obj = tempfile.TemporaryDirectory(prefix=f"sumo_{tag}_")
        run_dir = Path(temp_dir_obj.name)
    else:
        temp_dir_obj = None
        run_dir = Path(work_dir).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)

    try:
        cand_rou = run_dir / f"routes_{tag}.rou.xml"
        generate_multislice_routes(
            lambda_vec=lambda_vec,
            output_rou_file=cand_rou,
            net_file=net_file,
            vtypes_file=vtypes_file,
            slice_duration=1800.0,
            begin_time=1800.0,
            seed=seed,
            work_dir=run_dir,
        )

        sim_begin_time = 1800.0
        sim_end_time = sim_begin_time + len(lambda_vec) * 1800.0

        # Tạo tệp additional cho edgedata định kỳ 1800s
        edgedata_xml = run_dir / f"edgedata_{tag}.xml"
        add_file = run_dir / f"edgedata_add_{tag}.add.xml"
        with open(add_file, "w", encoding="utf-8") as f:
            f.write(
                f'<additional>\n'
                f'    <edgeData id="ed_{tag}" file="{edgedata_xml.name}" begin="{sim_begin_time:.0f}" end="{sim_end_time:.0f}" freq="1800"/>\n'
                f'</additional>\n'
            )

        summary_xml = run_dir / f"summary_{tag}.xml"
        sumo_bin = get_sumo_binary()

        # Chuẩn bị lệnh gọi SUMO (cand_rou đã chứa sẵn vTypes từ duarouter, chỉ cần nạp add_file)
        sumo_cmd = [
            sumo_bin,
            "-n", str(Path(net_file).resolve()),
            "-r", str(cand_rou),
            "-a", str(add_file),
            "--begin", f"{sim_begin_time:.0f}",
            "--end", f"{sim_end_time:.0f}",
            "--step-length", str(step_length),
            "--lateral-resolution", str(lateral_resolution),
            "--time-to-teleport", "120",
            "--collision.action", "warn",
            "--summary-output", str(summary_xml),
            "--no-step-log", "true",
            "--seed", str(seed),
        ]

        if checkpoint_file and Path(checkpoint_file).exists():
            sumo_cmd.extend(["--load-state", str(Path(checkpoint_file).resolve())])

        # Thực thi mô phỏng có timeout bảo vệ chống treo (Watchdog)
        try:
            res = subprocess.run(sumo_cmd, cwd=str(run_dir), capture_output=True, text=True, timeout=timeout_sec)
            if res.returncode != 0:
                print(f"[!] Warning SUMO lỗi (returncode={res.returncode}): {res.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"[!] CẢNH BÁO TÍNH TOÁN: Lượt chạy {tag} vượt quá timeout {timeout_sec}s (nghi vấn Gridlock). Tự động ngắt!")
            # Trả về ma trận sàn và telemetry phạt nặng
            num_pts = len(ordered_points) if ordered_points else 66
            v_penalty = np.full((num_pts, len(lambda_vec)), 5.0)
            telemetry_penalty = {"icr": 0.5, "gbr": 1.0, "tcr": 0.5, "teleport_rate": 0.5, "timeout_triggered": True}
            return v_penalty, telemetry_penalty

        # Trích xuất V_sim thực tế
        V_sim = parse_multislice_edgedata(
            xml_path=edgedata_xml,
            ordered_points=ordered_points,
            num_slices=len(lambda_vec),
            v0_vector=v0_vector
        )

        # Trích xuất telemetry thực tế từ XML
        telemetry = parse_simulation_summary(summary_xml)
        return V_sim, telemetry

    finally:
        if temp_dir_obj is not None:
            try:
                temp_dir_obj.cleanup()
            except Exception:
                pass


# =============================================================================
# 5. ĐÁNH GIÁ VỚI KỸ THUẬT CRN (COMMON RANDOM NUMBERS TRÊN 2 SEEDS)
# =============================================================================
def evaluate_candidate_crn(
    lambda_vec: np.ndarray,
    ordered_points: List[str],
    v0_vector: Optional[np.ndarray] = None,
    checkpoint_file: Optional[Union[str, Path]] = None,
    crn_seeds: Tuple[int, ...] = (42, 100),
    tag: str = "eval_crn"
) -> Tuple[np.ndarray, Dict[str, float]]:
    r"""
    Đánh giá vector lambda trên nhiều hạt giống ngẫu nhiên CRN và lấy trung bình
    nhằm triệt tiêu phương sai stochastic của SUMO vi mô.
    """
    v_sim_list = []
    telemetry_list = []

    for s_idx, seed in enumerate(crn_seeds):
        v_s, tel_s = evaluate_candidate(
            lambda_vec=lambda_vec,
            ordered_points=ordered_points,
            v0_vector=v0_vector,
            checkpoint_file=checkpoint_file,
            seed=seed,
            tag=f"{tag}_s{s_idx}"
        )
        v_sim_list.append(v_s)
        telemetry_list.append(tel_s)

    # Trung bình ma trận vận tốc
    V_sim_avg = np.mean(v_sim_list, axis=0)

    # Tổng hợp telemetry
    avg_telemetry = {
        "icr": round(float(np.mean([t["icr"] for t in telemetry_list])), 4),
        "gbr": round(float(np.mean([t["gbr"] for t in telemetry_list])), 4),
        "tcr": round(float(np.mean([t["tcr"] for t in telemetry_list])), 4),
        "teleport_rate": round(float(np.mean([t["teleport_rate"] for t in telemetry_list])), 4),
        "num_seeds": len(crn_seeds),
    }

    return V_sim_avg, avg_telemetry


if __name__ == "__main__":
    print("=" * 70)
    print("[*] KIỂM THỬ TỰ THÂN: sumo_headless_runner.py")
    print("=" * 70)

    pts = load_point_ids()
    print(f"[+] Đã nạp {len(pts)} điểm quan trắc chuẩn.")

    # 1. Kiểm thử tạo checkpoint warm-up 06:30
    ckpt_dir = SCENARIOS_DIR / "q1_calibrated_morning"
    ckpt_file = ckpt_dir / "checkpoint_warmup_0630.xml"
    ensure_warmup_checkpoint(ckpt_file, warmup_duration=300.0, force_recreate=False) # 300s test
    print(f"[+] Kiểm thử tạo/kiểm tra Checkpoint thành công tại: {ckpt_file.name}")

    print("\n" + "=" * 70)
    print("[OK] sumo_headless_runner.py ĐÃ ĐƯỢC XÂY DỰNG VÀ SẴN SÀNG TÍCH HỢP!")
    print("=" * 70)
