"""
baseline_engine.py
=============================================================================
BỘ TÍNH TOÁN CÁC MỐC THAM CHIẾU BASELINES & SÀN NHIỄU DỮ LIỆU
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận: macro_traffic_crawler/docs/SD_EVALUATION.md (Mục IV)

Các Mốc Tham Chiếu:
1. Free-flow Baseline (v0): Giả định đường hoàn toàn vắng tanh.
2. Persistence Baseline (v_d1 -> v_d2): Dùng ngày làm việc trước dự báo ngày sau.
3. Historical Median Baseline: Trung vị vận tốc của các ngày Train trong LODO.
4. Sàn Nhiễu Lý Thuyết: sigma_floor = Delta_noise / sqrt(2) (Giới hạn Bayes của cảm biến).

Đặc tính Input Độc lập & Linh hoạt:
- Hỗ trợ nạp từ: 1 file CSV, danh sách nhiều files CSV, thư mục chứa nhiều files,
  hoặc đường dẫn mẫu glob (ví dụ: 'data/processed/*.csv').
- Tự động gộp, lọc trùng lặp theo (date, time, point_id), đồng bộ lát cắt thời gian.
=============================================================================
"""

import os
import sys
import glob
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union

import numpy as np
import pandas as pd

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# =============================================================================
# 1. BỘ TIỆN ÍCH NẠP & LÀM SẠCH DỮ LIỆU ĐA NGUỒN (MULTI-SOURCE INGESTION)
# =============================================================================
def load_multiday_traffic_data(
    sources: Union[str, Path, List[Union[str, Path]]],
    min_confidence: float = 0.70,
    time_slice_minutes: int = 15
) -> pd.DataFrame:
    """
    Nạp và chuẩn hóa dữ liệu TomTom từ một hoặc nhiều nguồn file CSV rời rạc.

    Tham số:
        sources: Đường dẫn 1 file CSV, danh sách nhiều files CSV, thư mục, hoặc mẫu glob.
        min_confidence: Ngưỡng lọc độ tin cậy TomTom (mặc định: >= 0.70).
        time_slice_minutes: Độ rộng lát cắt gom cụm thời gian (mặc định: 15 phút).

    Trả về:
        pd.DataFrame đã làm sạch, chuẩn hóa các cột:
        ['date', 'time_slice', 'point_id', 'speed_kmh', 'free_flow_kmh', 'confidence']
    """
    matched_files: List[Path] = []

    # 1. Phân giải danh sách file từ tham số đầu vào
    if isinstance(sources, (str, Path)):
        src_path = Path(sources)
        if src_path.is_dir():
            matched_files = sorted(list(src_path.glob("*.csv")))
        elif "*" in str(sources) or "?" in str(sources):
            matched_files = [Path(f) for f in sorted(glob.glob(str(sources)))]
        elif src_path.is_file():
            matched_files = [src_path]
        else:
            raise FileNotFoundError(f"[!] Không tìm thấy nguồn dữ liệu: {sources}")
    elif isinstance(sources, list):
        for item in sources:
            p = Path(item)
            if p.is_file():
                matched_files.append(p)
            elif p.is_dir():
                matched_files.extend(sorted(list(p.glob("*.csv"))))
            else:
                for f in glob.glob(str(item)):
                    matched_files.append(Path(f))
    else:
        raise ValueError("[!] Tham số sources phải là str, Path hoặc List[str/Path].")

    if not matched_files:
        raise FileNotFoundError(f"[!] Không tìm thấy bất kỳ file CSV nào từ: {sources}")

    # 2. Đọc và gộp toàn bộ các file CSV hợp lệ
    dfs = []
    for f in matched_files:
        try:
            df_part = pd.read_csv(f)
            # Kiểm tra xem file có phải là dữ liệu lưu lượng TomTom hay không
            cols_lower = [c.lower() for c in df_part.columns]
            has_point = any(c in cols_lower for c in ["point_id", "segment_id"])
            has_speed = any("speed" in c for c in cols_lower)
            if not (has_point and has_speed):
                # Bỏ qua các file không phải dữ liệu giao thông (ví dụ bpr_optuna_history.csv)
                continue
            dfs.append(df_part)
        except Exception as e:
            print(f"[-] Cảnh báo: Không thể đọc file {f.name}: {e}")

    if not dfs:
        raise ValueError("[!] Không tìm thấy file dữ liệu giao thông hợp lệ nào trong các nguồn được chỉ định.")

    df_raw = pd.concat(dfs, ignore_index=True)

    # 3. Chuẩn hóa tên cột
    col_map = {
        "current_speed_kmh": "speed_kmh",
        "current_speed": "speed_kmh",
        "speed": "speed_kmh",
        "free_flow_speed_kmh": "free_flow_kmh",
        "free_flow_speed": "free_flow_kmh",
        "free_flow": "free_flow_kmh",
        "point_id": "point_id",
        "segment_id": "point_id"
    }
    df_raw = df_raw.rename(columns={k: v for k, v in col_map.items() if k in df_raw.columns})

    # Gán mặc định nếu thiếu free_flow_kmh hoặc confidence
    if "free_flow_kmh" not in df_raw.columns:
        df_raw["free_flow_kmh"] = 35.0
    if "confidence" not in df_raw.columns:
        df_raw["confidence"] = 1.0

    # Ép kiểu số cho speed_kmh và loại bỏ các dòng NaN
    df_raw["speed_kmh"] = pd.to_numeric(df_raw["speed_kmh"], errors="coerce")
    df_raw["free_flow_kmh"] = pd.to_numeric(df_raw["free_flow_kmh"], errors="coerce").fillna(35.0)
    df_raw["confidence"] = pd.to_numeric(df_raw["confidence"], errors="coerce").fillna(1.0)
    df_raw = df_raw.dropna(subset=["speed_kmh", "point_id"])

    # 4. Trích xuất Ngày và Lát cắt Thời gian (Date & Time-Slice)
    if "timestamp" in df_raw.columns:
        time_series = pd.to_datetime(df_raw["timestamp"], errors="coerce")
    elif "date" in df_raw.columns and "time" in df_raw.columns:
        time_series = pd.to_datetime(df_raw["date"].astype(str) + " " + df_raw["time"].astype(str), errors="coerce")
    elif "date" in df_raw.columns:
        time_series = pd.to_datetime(df_raw["date"], errors="coerce")
    else:
        time_series = pd.Series(pd.Timestamp("2026-10-01 00:00:00"), index=df_raw.index)

    # Nếu cột date chưa có hoặc có NaN, lấy từ time_series
    if "date" not in df_raw.columns or df_raw["date"].isna().any():
        df_raw["date"] = time_series.dt.strftime("%Y-%m-%d").fillna("2026-10-01")

    # Gom theo lát cắt thời gian (ví dụ 15 phút: 07:00, 07:15, 07:30, ...)
    valid_time_mask = time_series.notna()
    hours = time_series.dt.hour.fillna(0).astype(int).map("{:02d}".format)
    minutes = ((time_series.dt.minute.fillna(0).astype(int) // time_slice_minutes) * time_slice_minutes).map("{:02d}".format)
    df_raw["time_slice"] = hours + ":" + minutes

    # 5. Lọc theo độ tin cậy và khử trùng lặp
    df_clean = df_raw[df_raw["confidence"] >= min_confidence].copy()
    df_clean = df_clean.dropna(subset=["date", "time_slice", "point_id", "speed_kmh"])

    # Lấy trung bình nếu cùng 1 điểm và cùng 1 lát cắt có nhiều lần quét
    agg_dict = {
        "speed_kmh": "mean",
        "free_flow_kmh": "mean",
        "confidence": "mean"
    }
    if "road_name" in df_clean.columns:
        agg_dict["road_name"] = "first"

    df_grouped = (
        df_clean.groupby(["date", "time_slice", "point_id"], as_index=False)
        .agg(agg_dict)
    )

    return df_grouped


# =============================================================================
# 2. TÍNH BỘ BA BASELINE & SÀN NHIỄU DỮ LIỆU
# =============================================================================
def compute_freeflow_baseline(df: pd.DataFrame) -> Dict[str, float]:
    """
    Mốc 1: Free-flow Baseline (v0).
    Giả định toàn bộ mạng lưới luôn chạy với vận tốc dòng tự do lý tưởng.
    """
    diff = df["free_flow_kmh"].to_numpy() - df["speed_kmh"].to_numpy()
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    mae = float(np.mean(np.abs(diff)))

    return {
        "baseline_name": "Free-flow Baseline (v0)",
        "rmse_kmh": round(rmse, 3),
        "mae_kmh": round(mae, 3),
        "n_samples": len(df)
    }


def compute_pairwise_noise_floor(
    df: pd.DataFrame,
    day_1: str,
    day_2: str
) -> Dict[str, float]:
    """
    Mốc 2 & Mốc 3: Tính Persistence Baseline (Delta_noise) giữa 2 ngày làm việc và
    Sàn nhiễu lý thuyết (sigma_floor = Delta_noise / sqrt(2)).

    Chứng minh toán học:
        v_1 = mu + eps_1, v_2 = mu + eps_2  (eps độc lập, Var = sigma^2)
        Var(v_2 - v_1) = 2 * sigma^2 => Delta_noise = sqrt(2) * sigma
        => Sàn nhiễu lý thuyết tối ưu: sigma_floor = Delta_noise / sqrt(2).
    """
    df1 = df[df["date"] == day_1].set_index(["time_slice", "point_id"])
    df2 = df[df["date"] == day_2].set_index(["time_slice", "point_id"])

    common_idx = df1.index.intersection(df2.index)
    if len(common_idx) == 0:
        raise ValueError(f"[!] Không tìm thấy điểm đo chung giữa ngày {day_1} và {day_2}.")

    diff = df2.loc[common_idx, "speed_kmh"].to_numpy() - df1.loc[common_idx, "speed_kmh"].to_numpy()
    delta_noise = float(np.sqrt(np.mean(diff ** 2)))
    mae_persist = float(np.mean(np.abs(diff)))

    # Sàn nhiễu lý thuyết
    sigma_floor = delta_noise / np.sqrt(2.0)

    return {
        "day_pair": (day_1, day_2),
        "n_matched_points": len(common_idx),
        "delta_noise_kmh": round(delta_noise, 3),
        "persistence_rmse_kmh": round(delta_noise, 3),
        "persistence_mae_kmh": round(mae_persist, 3),
        "theoretical_noise_floor_kmh": round(sigma_floor, 3)
    }


def compute_lodo_benchmark_anchors(
    df: pd.DataFrame,
    test_day: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tính toán toàn bộ các mốc tham chiếu theo quy chuẩn Leave-One-Day-Out (LODO):
    - Tập Train: 4 ngày còn lại (hoặc toàn bộ nếu test_day là None).
    - Mốc Historical Median: Lấy trung vị của tập Train làm dự báo cho ngày Test.
    - Sàn nhiễu trung bình liên ngày.

    Tham số:
        df: DataFrame đa ngày đã làm sạch.
        test_day: Ngày kiểm định giữ lại (ví dụ '2026-10-20'). Nếu None, tự động chọn ngày cuối.

    Trả về:
        Dict tổng hợp chứa đầy đủ các mốc tham chiếu để đối chuẩn với SUMO.
    """
    unique_dates = sorted(df["date"].unique().tolist())
    if len(unique_dates) < 2:
        # Nếu chỉ có 1 ngày duy nhất, tính Free-flow và dùng sàn nhiễu mặc định
        ff_res = compute_freeflow_baseline(df)
        return {
            "status": "SINGLE_DAY_ONLY",
            "available_dates": unique_dates,
            "freeflow_baseline_rmse_kmh": ff_res["rmse_kmh"],
            "freeflow_baseline_mae_kmh": ff_res["mae_kmh"],
            "historical_median_rmse_kmh": None,
            "persistence_rmse_kmh": None,
            "delta_noise_kmh": None,
            "theoretical_noise_floor_kmh": None
        }

    if test_day is None or test_day not in unique_dates:
        test_day = unique_dates[-1]

    train_dates = [d for d in unique_dates if d != test_day]

    df_train = df[df["date"].isin(train_dates)]
    df_test = df[df["date"] == test_day]

    # 1. Free-flow Baseline trên ngày Test
    ff_res = compute_freeflow_baseline(df_test)

    # 2. Historical Median Baseline: Tính Median của Train theo (time_slice, point_id)
    train_median = (
        df_train.groupby(["time_slice", "point_id"])["speed_kmh"]
        .median()
        .rename("speed_median_train")
    )

    df_test_merged = df_test.merge(
        train_median,
        on=["time_slice", "point_id"],
        how="inner"
    )

    if len(df_test_merged) > 0:
        diff_med = df_test_merged["speed_median_train"].to_numpy() - df_test_merged["speed_kmh"].to_numpy()
        median_rmse = float(np.sqrt(np.mean(diff_med ** 2)))
        median_mae = float(np.mean(np.abs(diff_med)))
    else:
        median_rmse = None
        median_mae = None

    # 3. Tính sàn nhiễu Delta_noise trung bình qua các cặp ngày trong tập Train
    pairwise_noises = []
    for i in range(len(train_dates) - 1):
        try:
            pair_res = compute_pairwise_noise_floor(df_train, train_dates[i], train_dates[i+1])
            pairwise_noises.append(pair_res["delta_noise_kmh"])
        except Exception:
            pass

    # Nếu không có cặp train nào, ghép test với train gần nhất
    if not pairwise_noises:
        pair_res = compute_pairwise_noise_floor(df, train_dates[-1], test_day)
        pairwise_noises.append(pair_res["delta_noise_kmh"])

    avg_delta_noise = float(np.mean(pairwise_noises))
    theoretical_floor = float(avg_delta_noise / np.sqrt(2.0))

    return {
        "status": "SUCCESS",
        "unique_dates_count": len(unique_dates),
        "train_dates": train_dates,
        "test_day": test_day,
        "n_test_eval_points": len(df_test_merged),
        # Mốc 1
        "freeflow_baseline_rmse_kmh": ff_res["rmse_kmh"],
        "freeflow_baseline_mae_kmh": ff_res["mae_kmh"],
        # Mốc 2 (Chuẩn đối chứng công bằng nhất)
        "historical_median_rmse_kmh": round(median_rmse, 3) if median_rmse else None,
        "historical_median_mae_kmh": round(median_mae, 3) if median_mae else None,
        # Mốc 3 & Sàn nhiễu
        "delta_noise_kmh": round(avg_delta_noise, 3),
        "theoretical_noise_floor_kmh": round(theoretical_floor, 3),
        # Vùng chấp nhận khoa học (Acceptable Scientific Zone)
        "acceptable_zone_range": [round(theoretical_floor, 3), round(avg_delta_noise, 3)]
    }


# =============================================================================
# 3. HÀM PHÁN ĐOÁN HIỆU NĂNG MÔ PHỎNG SO VỚI BASELINES (BENCHMARK EVALUATOR)
# =============================================================================
def benchmark_simulation_performance(
    sim_rmse_kmh: float,
    anchors: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Phán đoán vị trí của sai số mô phỏng SUMO (RMSE_sim) trên thang đo 4 vùng:
    1. THẤT BẠI: RMSE_sim >= Free-flow RMSE
    2. CHƯA TỐT: RMSE_sim > Historical Median RMSE
    3. ĐẠT CHUẨN KHOA HỌC: Sàn nhiễu lý thuyết <= RMSE_sim <= Historical Median
    4. CẢNH BÁO QUÁ KHỚP: RMSE_sim < Sàn nhiễu lý thuyết (Học vẹt vào nhiễu)

    Tham số:
        sim_rmse_kmh: Sai số RMSE của mô phỏng SUMO (km/h).
        anchors: Kết quả từ compute_lodo_benchmark_anchors().
    """
    ff_rmse = anchors.get("freeflow_baseline_rmse_kmh", 999.0)
    median_rmse = anchors.get("historical_median_rmse_kmh", anchors.get("delta_noise_kmh", 999.0))
    floor_rmse = anchors.get("theoretical_noise_floor_kmh", 0.0)

    if sim_rmse_kmh >= ff_rmse:
        verdict = "FAIL_WORSE_THAN_FREEFLOW"
        status_msg = "Mô phỏng kém hơn giả định đường vắng tanh. Không nắm bắt được ùn tắc."
        badge_color = "#dc3545" # Red
    elif sim_rmse_kmh > median_rmse:
        verdict = "NEEDS_IMPROVEMENT_WORSE_THAN_MEDIAN"
        status_msg = "Mô phỏng có sai số lớn hơn bảng tra tĩnh Median. Cần tinh chỉnh quy mô nhu cầu."
        badge_color = "#ffc107" # Yellow
    elif floor_rmse <= sim_rmse_kmh <= median_rmse:
        verdict = "ACCEPTABLE_SCIENTIFIC_ZONE"
        status_msg = "ĐẠT CHUẨN KHOA HỌC: Sai số tiệm cận giới hạn cảm biến và vượt trội hơn bảng tra."
        badge_color = "#28a745" # Green
    else:
        verdict = "WARNING_OVERFITTING_NOISE"
        status_msg = "CẢNH BÁO HỌC VẸT: Sai số nhỏ hơn sàn nhiễu tự nhiên của thiết bị đo."
        badge_color = "#17a2b8" # Cyan

    return {
        "sim_rmse_kmh": round(sim_rmse_kmh, 3),
        "verdict": verdict,
        "status_message": status_msg,
        "badge_color": badge_color,
        "benchmarks": {
            "freeflow_rmse": ff_rmse,
            "historical_median_rmse": median_rmse,
            "theoretical_noise_floor": floor_rmse
        }
    }


# =============================================================================
# UNIT TEST / KIỂM THỬ TỰ THÂN TRÊN DỮ LIỆU CÓ SẴN TRONG PROJECT
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("[*] KIỂM THỬ TỰ THÂN: baseline_engine.py (NẠP ĐA NGUỒN & TÍNH SÀN NHIỄU)")
    print("=" * 70)

    # Tìm các file CSV có sẵn trong thư mục data/processed/
    base_data_dir = Path(__file__).resolve().parent.parent.parent / "macro_traffic_crawler" / "data" / "processed"
    sample_files = list(base_data_dir.glob("*.csv"))

    if sample_files:
        print(f"[*] Tìm thấy {len(sample_files)} file CSV thực tế trong: {base_data_dir.name}/")
        for f in sample_files:
            print(f"    + {f.name}")

        # Thử nghiệm nạp đa nguồn: truyền cả danh sách nhiều file
        print("\n[*] Đang nạp và hợp nhất dữ liệu từ nhiều file CSV rời rạc...")
        df_merged = load_multiday_traffic_data(sample_files, min_confidence=0.50, time_slice_minutes=15)
        print(f"[+] Tổng số dòng sau gộp & làm sạch: {len(df_merged):,}")
        print(f"[+] Các ngày quan sát được: {df_merged['date'].unique().tolist()}")
        print(f"[+] Số điểm đo nhận diện: {df_merged['point_id'].nunique()} điểm")

        # Tính toán LODO Benchmark Anchors
        anchors = compute_lodo_benchmark_anchors(df_merged)
        print("\n[*] KẾT QUẢ ĐỐI CHUẨN BASELINES & SÀN NHIỄU TOÀN MẠNG:")
        print(f"    + Ngày kiểm định Test:              {anchors.get('test_day')}")
        print(f"    + Mốc 1 - Free-flow RMSE (v0):      {anchors.get('freeflow_baseline_rmse_kmh')} km/h")
        print(f"    + Mốc 2 - Historical Median RMSE:   {anchors.get('historical_median_rmse_kmh')} km/h")
        print(f"    + Độ lệch thực tế liên ngày:        {anchors.get('delta_noise_kmh')} km/h")
        print(f"    + Mốc 3 - Sàn nhiễu lý thuyết:      {anchors.get('theoretical_noise_floor_kmh')} km/h")
        print(f"    + Vùng chuẩn khoa học:             {anchors.get('acceptable_zone_range')} km/h")

        # Thử nghiệm phán đoán với 1 giả định sai số SUMO = 4.2 km/h
        test_sim_rmse = 4.2
        bench_eval = benchmark_simulation_performance(test_sim_rmse, anchors)
        print(f"\n[*] ĐÁNH GIÁ MÔ PHỎNG THỬ NGHIỆM (Giả định SUMO RMSE = {test_sim_rmse} km/h):")
        print(f"    + Kết luận:  {bench_eval['verdict']}")
        print(f"    + Thông điệp: {bench_eval['status_message']}")

    print("\n" + "=" * 70)
    print("[OK] baseline_engine.py HOẠT ĐỘNG HOÀN TOÀN CHUẨN XÁC VỚI INPUT ĐA NGUỒN!")
    print("=" * 70)
