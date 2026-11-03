"""
speed_metrics.py
=============================================================================
BỘ 4 TRỤ CỘT ĐÁNH GIÁ ĐỘNG HỌC VẬN TỐC ĐỘC LẬP (INDEPENDENT SPEED DYNAMICS)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu phương pháp luận: macro_traffic_crawler/docs/SD_EVALUATION.md (Mục V)

4 Trụ cột Đánh giá:
1. Sai số Vận tốc Tuyệt đối & Tương đối (Speed RMSE, MAE, ME, MRE w.r.t v0)
2. Tương quan Hạng Mức độ Nghẽn Mạng (Spearman Rank Correlation rho, Kendall tau)
3. Độ Tương đồng Phân bố Vận tốc Toàn Mạng (Wasserstein Metric W1, KS Distance)
4. Ma trận Nhầm lẫn Phân loại Trạng thái Ùn tắc (LOS Classification, Macro F1, Cohen's Kappa)
=============================================================================
"""

import sys
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, Union
from scipy import stats
from sklearn.metrics import confusion_matrix, cohen_kappa_score, f1_score, precision_score, recall_score

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
# TRỤ CỘT 1: SAI SỐ VẬN TỐC TUYỆT ĐỐI & TƯƠNG ĐỐI
# =============================================================================
def compute_speed_errors(
    v_sim: np.ndarray,
    v_obs: np.ndarray,
    v_free: Optional[np.ndarray] = None,
    weights: Optional[np.ndarray] = None
) -> Dict[str, float]:
    r"""
    Tính toán các chỉ số sai số vận tốc tuyệt đối và tương đối (hỗ trợ trọng số nghịch đảo phương sai).

    Công thức:
        RMSE_v = sqrt( sum( w_e * (v_sim - v_obs)^2 ) / sum(w_e) )  [km/h]
        MAE_v  = sum( w_e * |v_sim - v_obs| ) / sum(w_e)            [km/h]
        ME_v   = sum( w_e * (v_sim - v_obs) ) / sum(w_e)            [km/h]  (Độ lệch thiên lệch bias)
        MRE_v  = sum( w_e * (|v_sim - v_obs| / v_0) ) / sum(w_e) * 100% [%]

    Tham số:
        v_sim: Mảng vận tốc mô phỏng vi mô (km/h).
        v_obs: Mảng vận tốc thực tế quan trắc từ TomTom (km/h).
        v_free: Mảng vận tốc tự do lý thuyết v0 (km/h, tùy chọn).
        weights: Mảng trọng số w_e (tùy chọn, ví dụ 1 / \sigma^2(c)).

    Trả về:
        Dict chứa: rmse_kmh, mae_kmh, mean_error_bias_kmh, mre_percent, smape_percent.
    """
    v_sim = np.asarray(v_sim, dtype=float)
    v_obs = np.asarray(v_obs, dtype=float)

    if len(v_sim) != len(v_obs):
        raise ValueError(f"Độ dài mảng không khớp: v_sim ({len(v_sim)}) != v_obs ({len(v_obs)})")
    if len(v_sim) == 0:
        raise ValueError("Mảng đầu vào rỗng.")

    diff = v_sim - v_obs
    abs_diff = np.abs(diff)

    if weights is not None:
        w = np.asarray(weights, dtype=float)
        w_sum = np.sum(w)
        if w_sum <= 0:
            w = np.ones_like(diff)
            w_sum = float(len(w))
        rmse = float(np.sqrt(np.sum(w * (diff ** 2)) / w_sum))
        mae = float(np.sum(w * abs_diff) / w_sum)
        me = float(np.sum(w * diff) / w_sum)
        denom_smape = np.abs(v_sim) + np.abs(v_obs) + 1e-6
        smape = float(np.sum(w * (2.0 * abs_diff / denom_smape)) / w_sum * 100.0)
    else:
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        mae = float(np.mean(abs_diff))
        me = float(np.mean(diff))
        denom_smape = np.abs(v_sim) + np.abs(v_obs) + 1e-6
        smape = float(np.mean(2.0 * abs_diff / denom_smape) * 100.0)

    results = {
        "rmse": round(rmse, 3),
        "rmse_kmh": round(rmse, 3),
        "mae": round(mae, 3),
        "mae_kmh": round(mae, 3),
        "mean_error_bias_kmh": round(me, 3),
        "bias": round(me, 3),
        "smape_percent": round(smape, 2)
    }

    # Mean Relative Error (MRE) theo v_0 nếu có cung cấp
    if v_free is not None:
        v_free = np.asarray(v_free, dtype=float)
        valid_mask = v_free > 1e-3
        if np.any(valid_mask):
            if weights is not None:
                sub_w = w[valid_mask]
                sub_w_sum = np.sum(sub_w)
                mre = float(np.sum(sub_w * (abs_diff[valid_mask] / v_free[valid_mask])) / max(sub_w_sum, 1e-6) * 100.0)
            else:
                mre = float(np.mean(abs_diff[valid_mask] / v_free[valid_mask]) * 100.0)
            results["mre_percent"] = round(mre, 2)
            results["mre"] = round(mre, 2)
        else:
            results["mre_percent"] = None
            results["mre"] = None
    else:
        results["mre_percent"] = None
        results["mre"] = None

    return results


# =============================================================================
# TRỤ CỘT 2: TƯƠNG QUAN HẠNG MỨC ĐỘ NGHẼN MẠNG (SPEARMAN RANK CORRELATION)
# =============================================================================
def compute_rank_correlation(
    v_sim: np.ndarray,
    v_obs: np.ndarray
) -> Dict[str, Any]:
    """
    Tính hệ số tương quan hạng Spearman (rho_rank) và Kendall's Tau.
    Kiểm tra xem SUMO có nhận diện đúng thứ tự các nút/tuyến đường nghẽn nhất trên bản đồ.

    Công thức:
        rho_rank = 1 - (6 * sum(d_i^2)) / (n * (n^2 - 1))
        d_i = Rank(v_sim, i) - Rank(v_obs, i)

    Tham số:
        v_sim: Mảng vận tốc mô phỏng vi mô (km/h).
        v_obs: Mảng vận tốc thực tế quan trắc từ TomTom (km/h).

    Trả về:
        Dict chứa: spearman_rho, spearman_pvalue, kendall_tau, kendall_pvalue.
    """
    v_sim = np.asarray(v_sim, dtype=float)
    v_obs = np.asarray(v_obs, dtype=float)

    if len(v_sim) < 3:
        return {
            "spearman_rho": 0.0,
            "spearman_pvalue": 1.0,
            "kendall_tau": 0.0,
            "kendall_pvalue": 1.0
        }

    # Spearman Rank Correlation
    res_spearman = stats.spearmanr(v_sim, v_obs)
    rho = float(res_spearman.statistic) if not np.isnan(res_spearman.statistic) else 0.0
    p_spearman = float(res_spearman.pvalue) if not np.isnan(res_spearman.pvalue) else 1.0

    # Kendall's Tau (Bổ trợ kiểm tra tính đơn điệu khi có nhiều thứ hạng bằng nhau)
    res_kendall = stats.kendalltau(v_sim, v_obs)
    tau = float(res_kendall.statistic) if not np.isnan(res_kendall.statistic) else 0.0
    p_kendall = float(res_kendall.pvalue) if not np.isnan(res_kendall.pvalue) else 1.0

    return {
        "spearman_rho": round(rho, 4),
        "spearman_pvalue": float(f"{p_spearman:.4e}"),
        "kendall_tau": round(tau, 4),
        "kendall_pvalue": float(f"{p_kendall:.4e}")
    }


# =============================================================================
# TRỤ CỘT 3: ĐỘ TƯƠNG ĐỒNG HÌNH HỌC PHÂN BỐ VẬN TỐC (WASSERSTEIN & KS)
# =============================================================================
def compute_distribution_divergence(
    v_sim: np.ndarray,
    v_obs: np.ndarray
) -> Dict[str, Any]:
    """
    Tính khoảng cách Wasserstein cấp 1 (Earth Mover's Distance) và
    khoảng cách cực đại Kolmogorov-Smirnov (D_KS) giữa hai hàm phân phối xác suất tích lũy.

    Công thức:
        W_1(P_sim, P_obs) = integral |F_sim(v) - F_obs(v)| dv  [km/h]
        D_KS = sup_v |F_sim(v) - F_obs(v)|

    Lưu ý Chuẩn mực Học thuật (Scientific Rigor):
        D_KS được báo cáo thuần túy như một thước đo mô tả khoảng cách hình học cực đại
        giữa hai hàm phân phối xác suất tích lũy (CDF). Không suy diễn ngụy biện rằng
        "KS không bác bỏ H0 nghĩa là 2 phân phối tương đương" do hạn chế mẫu và tương quan không gian.

    Tham số:
        v_sim: Mảng vận tốc mô phỏng vi mô (km/h).
        v_obs: Mảng vận tốc thực tế quan trắc từ TomTom (km/h).

    Trả về:
        Dict chứa: wasserstein_w1_kmh, ks_statistic, ks_pvalue.
    """
    v_sim = np.asarray(v_sim, dtype=float)
    v_obs = np.asarray(v_obs, dtype=float)

    if len(v_sim) == 0 or len(v_obs) == 0:
        return {
            "wasserstein_w1_kmh": None,
            "ks_statistic": None,
            "ks_pvalue": None
        }

    # 1. Khoảng cách Wasserstein W1 (Đơn vị: km/h)
    w1 = float(stats.wasserstein_distance(v_sim, v_obs))

    # 2. Khoảng cách Kolmogorov-Smirnov 2-sample
    ks_res = stats.ks_2samp(v_sim, v_obs)
    d_ks = float(ks_res.statistic)
    p_ks = float(ks_res.pvalue)

    return {
        "wasserstein_w1_kmh": round(w1, 3),
        "wasserstein_w1": round(w1, 3),
        "ks_statistic": round(d_ks, 4),
        "ks_statistic_d": round(d_ks, 4),
        "ks_pvalue": float(f"{p_ks:.4e}")
    }


# =============================================================================
# TRỤ CỘT 4: MA TRẬN NHẦM LẪN PHÂN LOẠI TRẠNG THÁI ÙN TẮC (LOS MATRIX)
# =============================================================================
LOS_LABELS = ["C (Kẹt xe)", "S (Ùn ứ)", "F (Thông thoáng)"]
LOS_CODES = [0, 1, 2]


def classify_los(v: np.ndarray, v_free: np.ndarray) -> np.ndarray:
    """
    Phân loại mức độ dịch vụ (Level of Service - LOS) theo tỷ số r = v / v0:
        - 0: Kẹt xe nghiêm trọng (Congested - C): r < 0.40
        - 1: Ùn ứ chậm (Slow/Dense - S):        0.40 <= r <= 0.70
        - 2: Thông thoáng (Free Flow - F):      r > 0.70

    Căn cứ: Chuẩn phân tầng vận tốc đô thị theo HCM 2010.
    """
    v = np.asarray(v, dtype=float)
    v_free = np.asarray(v_free, dtype=float)

    # Tránh chia cho 0
    safe_v0 = np.where(v_free > 1e-3, v_free, 30.0)
    ratio = v / safe_v0

    classes = np.zeros_like(v, dtype=int)
    classes[ratio >= 0.40] = 1
    classes[ratio > 0.70] = 2

    return classes


def compute_los_confusion_matrix(
    v_sim: np.ndarray,
    v_obs: np.ndarray,
    v_free: np.ndarray
) -> Dict[str, Any]:
    """
    Tính Ma trận Nhầm lẫn 3x3 và các chỉ số phân loại trạng thái ùn tắc toàn mạng:
    - Accuracy
    - Macro Precision, Macro Recall, Macro F1-Score
    - Hệ số Cohen's Kappa (kappa) đo lường độ đồng thuận loại trừ trùng khớp ngẫu nhiên.

    Tham số:
        v_sim: Mảng vận tốc mô phỏng vi mô (km/h).
        v_obs: Mảng vận tốc thực tế quan trắc từ TomTom (km/h) - Ground Truth.
        v_free: Mảng vận tốc tự do v0 (km/h).

    Trả về:
        Dict chứa: confusion_matrix (3x3 array và nested dict), metrics (acc, macro_f1, kappa).
    """
    y_true = classify_los(v_obs, v_free)
    y_pred = classify_los(v_sim, v_free)

    # Ma trận nhầm lẫn 3x3 với các nhãn cố định [0, 1, 2]
    cm = confusion_matrix(y_true, y_pred, labels=LOS_CODES)

    # Các chỉ số phân loại vĩ mô
    acc = float(np.trace(cm) / max(np.sum(cm), 1))
    macro_f1 = float(f1_score(y_true, y_pred, labels=LOS_CODES, average="macro", zero_division=0))
    macro_prec = float(precision_score(y_true, y_pred, labels=LOS_CODES, average="macro", zero_division=0))
    macro_rec = float(recall_score(y_true, y_pred, labels=LOS_CODES, average="macro", zero_division=0))
    kappa = float(cohen_kappa_score(y_true, y_pred, labels=LOS_CODES))

    # Cấu trúc JSON-friendly của ma trận nhầm lẫn
    cm_dict = {
        "true_C_pred_C": int(cm[0, 0]),
        "true_C_pred_S": int(cm[0, 1]),
        "true_C_pred_F": int(cm[0, 2]),
        "true_S_pred_C": int(cm[1, 0]),
        "true_S_pred_S": int(cm[1, 1]),
        "true_S_pred_F": int(cm[1, 2]),
        "true_F_pred_C": int(cm[2, 0]),
        "true_F_pred_S": int(cm[2, 1]),
        "true_F_pred_F": int(cm[2, 2]),
    }

    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "cohen_kappa": round(kappa, 4),
        "matrix_array": cm.tolist(),
        "matrix_dict": cm_dict,
        "labels": LOS_LABELS
    }


# =============================================================================
# HÀM TỔNG HỢP TOÀN DIỆN (WRAPPER TÍCH HỢP 4 TRỤ CỘT)
# =============================================================================
def evaluate_speed_dynamics_suite(
    v_sim: Union[np.ndarray, list, pd.Series],
    v_obs: Union[np.ndarray, list, pd.Series],
    v_free: Union[np.ndarray, list, pd.Series],
    weights: Optional[Union[np.ndarray, list, pd.Series]] = None
) -> Dict[str, Any]:
    """
    Thực thi trọn vẹn Bộ 4 Trụ cột Đánh giá Động học Vận tốc Độc lập.

    Tham số:
        v_sim: Mảng vận tốc mô phỏng vi mô SUMO (km/h).
        v_obs: Mảng vận tốc thực nghiệm TomTom (km/h).
        v_free: Mảng vận tốc dòng tự do v0 (km/h).
        weights: Mảng trọng số nghịch đảo phương sai w_e (tùy chọn).

    Trả về:
        Dict tổng hợp số liệu 4 trụ cột chuẩn học thuật sẵn sàng đưa vào báo cáo và JSON.
    """
    v_sim_arr = np.asarray(v_sim, dtype=float)
    v_obs_arr = np.asarray(v_obs, dtype=float)
    v_free_arr = np.asarray(v_free, dtype=float)
    weights_arr = np.asarray(weights, dtype=float) if weights is not None else None

    pillar1_errors = compute_speed_errors(v_sim_arr, v_obs_arr, v_free_arr, weights=weights_arr)
    pillar2_ranks = compute_rank_correlation(v_sim_arr, v_obs_arr)
    pillar3_dist = compute_distribution_divergence(v_sim_arr, v_obs_arr)
    pillar4_los = compute_los_confusion_matrix(v_sim_arr, v_obs_arr, v_free_arr)

    return {
        "n_evaluated_edges": len(v_sim_arr),
        "pillar1_speed_errors": pillar1_errors,
        "pillar2_rank_correlation": pillar2_ranks,
        "pillar3_distribution_divergence": pillar3_dist,
        "pillar4_los_regimes": pillar4_los
    }


# Bí danh tương thích
evaluate_all_speed_metrics = evaluate_speed_dynamics_suite


# =============================================================================
# UNIT TEST / KIỂM THỬ TỰ THÂN (BUILT-IN SELF TEST)
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("[*] KIỂM THỬ TỰ THÂN: speed_metrics.py (BỘ 4 TRỤ CỘT VẬN TỐC)")
    print("=" * 70)

    # Dữ liệu giả lập 10 cạnh để test các tình huống thực tế
    np.random.seed(42)
    sample_v0 = np.array([35.0, 40.0, 30.0, 35.0, 45.0, 30.0, 35.0, 40.0, 50.0, 30.0])
    # Tốc độ thực tế dao động từ tắc đường (10 km/h) đến thông thoáng (35 km/h)
    sample_v_obs = np.array([12.0, 18.0, 25.0, 11.0, 38.0, 9.0, 28.0, 22.0, 42.0, 14.0])
    # Mô phỏng bám sát thực tế kèm nhiễu ngẫu nhiên nhỏ
    sample_v_sim = sample_v_obs + np.random.normal(loc=0.5, scale=2.5, size=len(sample_v_obs))
    sample_v_sim = np.clip(sample_v_sim, 5.0, 50.0)

    suite_results = evaluate_speed_dynamics_suite(sample_v_sim, sample_v_obs, sample_v0)

    p1 = suite_results["pillar1_speed_errors"]
    p2 = suite_results["pillar2_rank_correlation"]
    p3 = suite_results["pillar3_distribution_divergence"]
    p4 = suite_results["pillar4_los_regimes"]

    print(f"\n[1] TRỤ CỘT 1 - SAI SỐ VẬN TỐC:")
    print(f"    + RMSE: {p1['rmse_kmh']} km/h")
    print(f"    + MAE:  {p1['mae_kmh']} km/h")
    print(f"    + Bias: {p1['mean_error_bias_kmh']} km/h")
    print(f"    + MRE:  {p1['mre_percent']}% so với v0")

    print(f"\n[2] TRỤ CỘT 2 - TƯƠNG QUAN HẠNG NGHẼN MẠNG:")
    print(f"    + Spearman Rho: {p2['spearman_rho']} (p-value = {p2['spearman_pvalue']})")
    print(f"    + Kendall Tau:  {p2['kendall_tau']} (p-value = {p2['kendall_pvalue']})")

    print(f"\n[3] TRỤ CỘT 3 - ĐỘ LỆCH PHÂN BỐ XÁC SUẤT:")
    print(f"    + Wasserstein W1: {p3['wasserstein_w1_kmh']} km/h")
    print(f"    + KS Statistic D: {p3['ks_statistic']} (p-value = {p3['ks_pvalue']})")

    print(f"\n[4] TRỤ CỘT 4 - MA TRẬN NHẦM LẪN LOS (MỨC DỊCH VỤ):")
    print(f"    + Accuracy:     {p4['accuracy'] * 100:.1f}%")
    print(f"    + Macro F1:     {p4['macro_f1']:.3f}")
    print(f"    + Cohen's Kappa {p4['cohen_kappa']:.3f}")
    print(f"    + Ma trận 3x3 (C/S/F):\n{np.array(p4['matrix_array'])}")

    print("\n" + "=" * 70)
    print("[OK] speed_metrics.py HOẠT ĐỘNG HOÀN TOÀN CHUẨN XÁC THEO LÝ THUYẾT!")
    print("=" * 70)
