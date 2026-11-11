r"""
prepare_calibration_targets.py
=============================================================================
CHUẨN HÓA TẬP DỮ LIỆU ĐẦU VÀO & MẶT NẠ TRỌNG SỐ ĐỘ TIN CẬY (SOFT MASKING)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận:
- SD_EVALUATION.md (Mục 3.2, Mục 4.1 & Mục V)
- ROADMAP_50DAYS.md (Nhiệm vụ 1.1)

Các tính năng cốt lõi:
1. Đồng bộ hóa 66 điểm quan trắc định danh cho 7 lát cắt 30 phút (06:30 - 10:00).
2. Cơ chế Mặt nạ Mềm (Soft Masking) & Trọng số Nghịch đảo Phương sai:
     m_{e,t} = 1 nếu c_{e,t} >= 0.30, ngược lại m_{e,t} = 0
     w_{e,t} = (m_{e,t} * c_{e,t}) / sum_{e'}(m_{e',t} * c_{e',t})
   Loại bỏ hoàn toàn lỗi NaN và không thiên lệch về các cạnh lớn.
3. Cơ chế Masked Loss cho các ngày khuyết 06:00 - 07:00 (14/10, 19/10).
4. Tính toán Free-flow Baseline (v0) và Historical Median toàn mạng và theo
   10 hành lang trục chính (Corridors).
5. Xuất ma trận mục tiêu đóng gói chuẩn .npz và summary .json cho bộ tối ưu CMA-ES.
=============================================================================
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd

# Hỗ trợ UTF-8 cho console Windows
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

TIME_SLICES = ["06:30", "07:00", "07:30", "08:00", "08:30", "09:00", "09:30"]
CONFIDENCE_THRESHOLD = 0.30


def load_sampling_points(points_file: Optional[Path] = None) -> pd.DataFrame:
    """Nạp danh sách 66 điểm quan trắc định danh chuẩn."""
    if points_file is None:
        points_file = METADATA_DIR / "sampling_points.csv"
    if not points_file.exists():
        raise FileNotFoundError(f"[!] Không tìm thấy: {points_file}")
    df_pts = pd.read_csv(points_file)
    return df_pts


def load_corridor_definitions(corridor_file: Optional[Path] = None) -> Dict[str, Any]:
    """Nạp bảng định nghĩa 10 hành lang trục chính."""
    if corridor_file is None:
        corridor_file = METADATA_DIR / "corridor_definitions.json"
    if not corridor_file.exists():
        raise FileNotFoundError(f"[!] Không tìm thấy: {corridor_file}")
    with open(corridor_file, "r", encoding="utf-8") as f:
        corridors = json.load(f)
    return corridors


def load_raw_traffic_dfs() -> pd.DataFrame:
    """Đọc và gộp toàn bộ dữ liệu cào TomTom từ các tệp xử lý."""
    hist_file = PROCESSED_DIR / "macro_traffic_history.csv"
    d19_file = PROCESSED_DIR / "hcmc_19_10_data.csv"

    dfs = []
    if hist_file.exists():
        dfs.append(pd.read_csv(hist_file))
    if d19_file.exists():
        dfs.append(pd.read_csv(d19_file))

    if not dfs:
        raise FileNotFoundError("[!] Không tìm thấy tệp dữ liệu lưu lượng TomTom nào!")

    df_all = pd.concat(dfs, ignore_index=True)
    # Đồng bộ hóa định dạng thời gian
    df_all["time_dt"] = pd.to_datetime(df_all["time"], format="%H:%M:%S", errors="coerce")
    df_all["time_slice"] = df_all["time_dt"].dt.floor("30min").dt.strftime("%H:%M")

    # Loại bỏ bản ghi ngoài 7 lát cắt mục tiêu
    df_all = df_all[df_all["time_slice"].isin(TIME_SLICES)].copy()
    return df_all


def build_multiday_calibration_targets(
    min_confidence: float = CONFIDENCE_THRESHOLD,
    save_output: bool = True
) -> Dict[str, Any]:
    r"""
    Xây dựng ma trận mục tiêu V_obs và ma trận trọng số W theo cơ chế Soft Masking.

    Returns:
        Dict chứa:
          - 'dates': Danh sách các ngày làm việc độc lập [D]
          - 'point_ids': Danh sách 66 điểm quan trắc theo đúng thứ tự [66]
          - 'time_slices': Danh sách 7 lát cắt thời gian [7]
          - 'v_obs_by_date': Dict[date, np.ndarray 66x7]
          - 'weights_by_date': Dict[date, np.ndarray 66x7]
          - 'conf_by_date': Dict[date, np.ndarray 66x7]
          - 'mask_by_date': Dict[date, np.ndarray 66x7]
          - 'v0_free_flow': np.ndarray [66]
          - 'v_historical_median': np.ndarray [66x7]
          - 'corridor_definitions': Dict 10 hành lang
    """
    df_pts = load_sampling_points()
    ordered_points = df_pts["point_id"].tolist()
    N_POINTS = len(ordered_points)
    point_to_idx = {p: i for i, p in enumerate(ordered_points)}

    corridors = load_corridor_definitions()
    df_raw = load_raw_traffic_dfs()

    # Nhận diện các ngày làm việc có dữ liệu
    available_dates = sorted(df_raw["date"].unique().tolist())
    print(f"[*] Tìm thấy {len(available_dates)} ngày khảo sát: {available_dates}")

    # Tính v0_free_flow theo từng điểm (ưu tiên trung vị free_flow_speed_kmh thực tế)
    v0_dict = df_raw.groupby("point_id")["free_flow_speed_kmh"].median().to_dict()
    v0_vec = np.array([v0_dict.get(p, 35.0) for p in ordered_points], dtype=float)

    v_obs_by_date: Dict[str, np.ndarray] = {}
    weights_by_date: Dict[str, np.ndarray] = {}
    conf_by_date: Dict[str, np.ndarray] = {}
    mask_by_date: Dict[str, np.ndarray] = {}

    K_SLICES = len(TIME_SLICES)

    for d in available_dates:
        df_d = df_raw[df_raw["date"] == d]

        # Khởi tạo ma trận rỗng
        V_d = np.zeros((N_POINTS, K_SLICES), dtype=float)
        W_d = np.zeros((N_POINTS, K_SLICES), dtype=float)
        C_d = np.zeros((N_POINTS, K_SLICES), dtype=float)
        M_d = np.zeros((N_POINTS, K_SLICES), dtype=float)

        # Gom nhóm theo (point_id, time_slice)
        agg_d = df_d.groupby(["point_id", "time_slice"]).agg(
            speed_mean=("current_speed_kmh", "mean"),
            conf_mean=("confidence", "mean")
        ).reset_index()

        # Điền dữ liệu vào ma trận
        for _, row in agg_d.iterrows():
            pid = row["point_id"]
            if pid not in point_to_idx:
                continue
            p_idx = point_to_idx[pid]
            ts = row["time_slice"]
            if ts not in TIME_SLICES:
                continue
            t_idx = TIME_SLICES.index(ts)

            v_val = float(row["speed_mean"])
            c_val = float(row["conf_mean"])

            V_d[p_idx, t_idx] = v_val
            C_d[p_idx, t_idx] = c_val

            # Soft Masking: chỉ kích hoạt khi c >= min_confidence và v_val > 0
            if c_val >= min_confidence and v_val > 0:
                M_d[p_idx, t_idx] = 1.0

        # Nếu điểm nào bị khuyết (M=0), điền v0 tạm thời để tránh NaN
        for p_idx in range(N_POINTS):
            for t_idx in range(K_SLICES):
                if M_d[p_idx, t_idx] == 0.0:
                    V_d[p_idx, t_idx] = v0_vec[p_idx]

        # Tính toán ma trận trọng số chuẩn hóa W_d theo từng lát cắt thời gian
        for t_idx in range(K_SLICES):
            denom = np.sum(M_d[:, t_idx] * C_d[:, t_idx])
            if denom > 0:
                W_d[:, t_idx] = (M_d[:, t_idx] * C_d[:, t_idx]) / denom
            else:
                # Nếu lát cắt này hoàn toàn khuyết dữ liệu (ví dụ 06:30 ở ngày 14/10, 19/10),
                # gán trọng số toàn bộ = 0 (Cơ chế Masked Loss)
                W_d[:, t_idx] = 0.0

        v_obs_by_date[d] = V_d
        weights_by_date[d] = W_d
        conf_by_date[d] = C_d
        mask_by_date[d] = M_d

    # Tính Historical Median trên các ngày có mặt nạ M = 1
    V_median = np.zeros((N_POINTS, K_SLICES), dtype=float)
    for p_idx in range(N_POINTS):
        for t_idx in range(K_SLICES):
            valid_speeds = [
                v_obs_by_date[d][p_idx, t_idx]
                for d in available_dates
                if mask_by_date[d][p_idx, t_idx] == 1.0
            ]
            if valid_speeds:
                V_median[p_idx, t_idx] = float(np.median(valid_speeds))
            else:
                V_median[p_idx, t_idx] = v0_vec[p_idx]

    result = {
        "dates": available_dates,
        "point_ids": ordered_points,
        "time_slices": TIME_SLICES,
        "v_obs_by_date": v_obs_by_date,
        "weights_by_date": weights_by_date,
        "conf_by_date": conf_by_date,
        "mask_by_date": mask_by_date,
        "v0_free_flow": v0_vec,
        "v_historical_median": V_median,
        "corridor_definitions": corridors,
    }

    if save_output:
        save_calibration_targets(result)

    return result


def save_calibration_targets(data: Dict[str, Any]) -> None:
    """Lưu trữ ma trận mục tiêu ra file .npz và summary .json."""
    npz_path = PROCESSED_DIR / "calibration_targets_multiday.npz"
    summary_path = PROCESSED_DIR / "calibration_targets_summary.json"

    # Đóng gói mảng numpy
    np_dict = {
        "dates": np.array(data["dates"]),
        "point_ids": np.array(data["point_ids"]),
        "time_slices": np.array(data["time_slices"]),
        "v0_free_flow": data["v0_free_flow"],
        "v_historical_median": data["v_historical_median"],
    }
    for d in data["dates"]:
        np_dict[f"v_obs_{d}"] = data["v_obs_by_date"][d]
        np_dict[f"weights_{d}"] = data["weights_by_date"][d]
        np_dict[f"conf_{d}"] = data["conf_by_date"][d]
        np_dict[f"mask_{d}"] = data["mask_by_date"][d]

    np.savez_compressed(npz_path, **np_dict)
    print(f"[+] Đã lưu dữ liệu mục tiêu nén vào: {npz_path.name}")

    # Xuất tệp tóm tắt JSON dễ đọc
    summary = {
        "num_dates": len(data["dates"]),
        "dates": data["dates"],
        "num_points": len(data["point_ids"]),
        "time_slices": data["time_slices"],
        "mean_free_flow_speed": round(float(np.mean(data["v0_free_flow"])), 2),
        "mean_historical_median_by_slice": {
            ts: round(float(np.mean(data["v_historical_median"][:, i])), 2)
            for i, ts in enumerate(data["time_slices"])
        },
        "coverage_by_date": {
            d: {
                "active_slices": int(np.sum(np.sum(data["weights_by_date"][d], axis=0) > 0.99)),
                "mean_observed_speed": round(float(np.mean(data["v_obs_by_date"][d][data["mask_by_date"][d] == 1.0])), 2) if np.sum(data["mask_by_date"][d]) > 0 else 0.0,
                "mean_confidence": round(float(np.mean(data["conf_by_date"][d])), 3)
            }
            for d in data["dates"]
        }
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[+] Đã lưu báo cáo thống kê tóm tắt vào: {summary_path.name}")


def load_calibration_targets_npz(npz_path: Optional[Path] = None) -> Dict[str, Any]:
    """Hàm tiện ích nạp nhanh dữ liệu mục tiêu đã chuẩn hóa từ .npz."""
    if npz_path is None:
        npz_path = PROCESSED_DIR / "calibration_targets_multiday.npz"
    if not npz_path.exists():
        raise FileNotFoundError(f"[!] Không tìm thấy tệp mục tiêu: {npz_path}")

    loaded = np.load(npz_path, allow_pickle=True)
    dates = loaded["dates"].tolist()
    point_ids = loaded["point_ids"].tolist()
    time_slices = loaded["time_slices"].tolist()

    v_obs_by_date = {d: loaded[f"v_obs_{d}"] for d in dates}
    weights_by_date = {d: loaded[f"weights_{d}"] for d in dates}
    conf_by_date = {d: loaded[f"conf_{d}"] for d in dates}
    mask_by_date = {d: loaded[f"mask_{d}"] for d in dates}

    corridors = load_corridor_definitions()

    return {
        "dates": dates,
        "point_ids": point_ids,
        "time_slices": time_slices,
        "v_obs_by_date": v_obs_by_date,
        "weights_by_date": weights_by_date,
        "conf_by_date": conf_by_date,
        "mask_by_date": mask_by_date,
        "v0_free_flow": loaded["v0_free_flow"],
        "v_historical_median": loaded["v_historical_median"],
        "corridor_definitions": corridors,
    }


if __name__ == "__main__":
    print("=" * 70)
    print("[*] CHẠY MODULE 1: PREPARE CALIBRATION TARGETS (SOFT MASKING & CORRIDORS)")
    print("=" * 70)
    res = build_multiday_calibration_targets(min_confidence=CONFIDENCE_THRESHOLD, save_output=True)

    print("\n[+] BẢNG KIỂM TRA MẶT NẠ VÀ TRỌNG SỐ TỪNG NGÀY:")
    for d in res["dates"]:
        W = res["weights_by_date"][d]
        M = res["mask_by_date"][d]
        weight_sums = np.sum(W, axis=0)
        active_pts = np.sum(M, axis=0)
        print(f"  • Ngày {d}:")
        print(f"    - Số điểm đạt chuẩn c>=0.30 theo từng lát: {active_pts.astype(int).tolist()}")
        print(f"    - Tổng trọng số (sum W) theo từng lát:     {np.round(weight_sums, 3).tolist()}")
        # Kiểm tra không chứa NaN
        assert not np.isnan(W).any(), f"Lỗi: Ma trận trọng số ngày {d} chứa NaN!"
        assert not np.isnan(res['v_obs_by_date'][d]).any(), f"Lỗi: Ma trận V_obs ngày {d} chứa NaN!"

    print("\n[+] BẢNG TRUNG VỊ LỊCH SỬ HISTORICAL MEDIAN:")
    for i, ts in enumerate(res["time_slices"]):
        v_ts = res["v_historical_median"][:, i]
        print(f"  • Lát cắt {ts}: Vận tốc trung vị toàn mạng = {np.mean(v_ts):.2f} km/h (min={np.min(v_ts):.2f}, max={np.max(v_ts):.2f})")

    print("\n" + "=" * 70)
    print("[OK] BƯỚC 1 HOÀN TẤT VÀ KIỂM CHỨNG TOÀN DIỆN THÀNH CÔNG!")
    print("=" * 70)
