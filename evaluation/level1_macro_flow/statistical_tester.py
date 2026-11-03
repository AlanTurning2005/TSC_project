r"""
HỆ THỐNG KIỂM ĐỊNH THỐNG KÊ CHUẨN HỌC THUẬT (IEEE/TRB/ACM)
(Two-Tier Hierarchical Inference, LODO Paired t-Test & Spatial Cluster Bootstrap)

Mô đun thực thi các chuẩn mực suy diễn thống kê nghiêm ngặt theo quy chuẩn:
1. Phân rã thứ bậc 2 tầng (Two-Tier Hierarchical Design):
   - Tầng 1: Lấy trung bình 4 Simulation Seeds trong cùng 1 Demand Seed (khử phương sai vi mô).
   - Tầng 2: Suy diễn thống kê trên đúng J=5 Demand Seeds độc lập (tránh lỗi Giả lặp Pseudo-Replication).
   - Áp dụng phân phối Student-t với df = J - 1 = 4 (t_crit = 2.776 với 95% CI).
2. Kiểm định ngoại suy ngày giữ lại (Leave-One-Day-Out Paired t-Test):
   - So sánh trực tiếp trên từng ngày độc lập d in {1..5} giữa SUMO và Baseline Median.
   - Khử biến động ngẫu nhiên về thời tiết, triệt tiêu thiên lệch giữa các ngày.
3. Spatial Cluster Bootstrap theo Hành lang (Corridor Clusters):
   - Tái lấy mẫu có hoàn lại ở cấp độ cụm tuyến đường (Pasteur, Nam Kỳ Khởi Nghĩa, Hai Bà Trưng...),
     bảo toàn cấu trúc tự tương quan không gian (Spatial Autocorrelation).
"""

import sys
from typing import Dict, List, Tuple, Union, Callable, Optional, Any
import numpy as np
import pandas as pd
from scipy import stats

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def hierarchical_two_tier_ci(
    runs_df: pd.DataFrame,
    metric_col: str = "rmse",
    demand_seed_col: str = "demand_seed",
    sim_seed_col: str = "sim_seed",
    alpha: float = 0.05,
) -> Dict[str, Any]:
    r"""
    Tính khoảng tin cậy (1 - alpha) hai tầng thứ bậc chuẩn tắc, chống giả lặp (Pseudo-Replication).

    Công thức:
      Tầng 1 (Within-Demand Seed):
        \bar{Y}_j = \frac{1}{K} \sum_{k=1}^K Y_{j, k}  (với K là số sim seeds)
      Tầng 2 (Between-Demand Seeds):
        \bar{Y} = \frac{1}{J} \sum_{j=1}^J \bar{Y}_j   (với J là số demand seeds độc lập)
        S_{\text{macro}} = \sqrt{ \frac{1}{J-1} \sum_{j=1}^J (\bar{Y}_j - \bar{Y})^2 }
        CI_{1-\alpha} = \left[ \bar{Y} \pm t_{1-\alpha/2, J-1} \cdot \frac{S_{\text{macro}}}{\sqrt{J}} \right]

    Args:
        runs_df: DataFrame chứa kết quả chạy, tối thiểu gồm metric_col, demand_seed_col, sim_seed_col.
        metric_col: Tên cột chỉ số cần đánh giá (ví dụ 'rmse', 'mae', 'rho_rank').
        demand_seed_col: Tên cột định danh kịch bản nhu cầu vĩ mô.
        sim_seed_col: Tên cột định danh hạt giống ngẫu nhiên vi mô SUMO.
        alpha: Mức ý nghĩa thống kê (mặc định 0.05 cho 95% CI).

    Returns:
        Dict chứa đầy đủ tham số suy diễn: tier1_means, macro_mean, macro_std, df, t_crit, ci_lower, ci_upper.
    """
    if metric_col not in runs_df.columns:
        raise KeyError(f"Không tìm thấy cột chỉ số '{metric_col}' trong runs_df!")
    if demand_seed_col not in runs_df.columns:
        raise KeyError(f"Không tìm thấy cột '{demand_seed_col}' trong runs_df!")

    # Tầng 1: Lấy trung bình trong nội bộ từng Demand Seed
    tier1_group = runs_df.groupby(demand_seed_col)[metric_col].agg(["mean", "count", "std"]).reset_index()
    tier1_means = tier1_group["mean"].to_numpy()
    J = len(tier1_means)

    if J < 2:
        raise ValueError(f"Cần ít nhất 2 Demand Seeds độc lập để ước lượng phương sai vĩ mô (hiện có J={J})!")

    # Tầng 2: Suy diễn thống kê trên J quan sát độc lập
    macro_mean = float(np.mean(tier1_means))
    macro_std = float(np.std(tier1_means, ddof=1))
    standard_error = float(macro_std / np.sqrt(J))
    df = J - 1
    t_critical = float(stats.t.ppf(1.0 - alpha / 2.0, df=df))

    ci_margin = t_critical * standard_error
    ci_lower = macro_mean - ci_margin
    ci_upper = macro_mean + ci_margin

    return {
        "metric_name": metric_col,
        "num_demand_seeds": J,
        "sim_seeds_per_demand": tier1_group["count"].tolist(),
        "tier1_within_means": {
            str(row[demand_seed_col]): float(row["mean"]) for _, row in tier1_group.iterrows()
        },
        "macro_mean": round(macro_mean, 4),
        "macro_std": round(macro_std, 4),
        "standard_error": round(standard_error, 4),
        "degrees_of_freedom": df,
        "confidence_level": round((1.0 - alpha) * 100, 1),
        "t_critical": round(t_critical, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "ci_margin": round(ci_margin, 4),
        "ci_formatted": f"[{ci_lower:.3f}, {ci_upper:.3f}]",
        "academic_report": f"{macro_mean:.3f} ± {ci_margin:.3f} (95% CI, df={df}, t={t_critical:.3f})",
    }


def lodo_paired_test(
    daily_errors_model: Union[List[float], np.ndarray, Dict[str, float]],
    daily_errors_baseline: Union[List[float], np.ndarray, Dict[str, float]],
    model_name: str = "SUMO",
    baseline_name: str = "Historical_Median",
    alpha: float = 0.05,
) -> Dict[str, Any]:
    r"""
    Kiểm định giả thuyết ghép cặp cấp độ ngày ngoại suy (Leave-One-Day-Out Paired t-Test).

    Công thức:
      D_d = \text{Error}_{\text{model}}^{(d)} - \text{Error}_{\text{baseline}}^{(d)}  (cho từng ngày d)
      \bar{D} = \frac{1}{n} \sum_{d=1}^n D_d
      S_D = \sqrt{ \frac{1}{n-1} \sum_{d=1}^n (D_d - \bar{D})^2 }
      t = \frac{\bar{D}}{S_D / \sqrt{n}}, \quad df = n - 1

    Args:
        daily_errors_model: Sai số (ví dụ RMSE) của mô hình qua n ngày test giữ lại.
        daily_errors_baseline: Sai số của baseline tương ứng qua đúng n ngày đó.
        model_name: Tên mô hình đang kiểm định.
        baseline_name: Tên baseline đối chuẩn.
        alpha: Mức ý nghĩa thống kê (0.05).

    Returns:
        Dict chứa kết quả kiểm định t, p-value, và kết luận học thuật.
    """
    # Đồng bộ đầu vào dạng mảng
    if isinstance(daily_errors_model, dict) and isinstance(daily_errors_baseline, dict):
        common_days = sorted(list(set(daily_errors_model.keys()) & set(daily_errors_baseline.keys())))
        if len(common_days) < 2:
            raise ValueError("Không đủ số ngày chung giữa Model và Baseline để kiểm định ghép cặp!")
        y_model = np.array([daily_errors_model[d] for d in common_days], dtype=float)
        y_base = np.array([daily_errors_baseline[d] for d in common_days], dtype=float)
        days_list = common_days
    else:
        y_model = np.array(daily_errors_model, dtype=float)
        y_base = np.array(daily_errors_baseline, dtype=float)
        if len(y_model) != len(y_base):
            raise ValueError(f"Độ dài mẫu không khớp: Model({len(y_model)}) vs Baseline({len(y_base)})!")
        days_list = [f"Day_{i+1}" for i in range(len(y_model))]

    n = len(y_model)
    if n < 2:
        raise ValueError(f"Cần ít nhất 2 ngày độc lập (hiện có n={n})!")

    # Tính hiệu số ghép cặp D_d = Error_model - Error_baseline
    # (Nếu D_d < 0 nghĩa là Model có sai số nhỏ hơn -> Model tốt hơn Baseline)
    diffs = y_model - y_base
    mean_diff = float(np.mean(diffs))
    std_diff = float(np.std(diffs, ddof=1))
    se_diff = float(std_diff / np.sqrt(n))
    df = n - 1

    # Tránh chia cho 0 nếu sai số giống hệt nhau
    if std_diff < 1e-12:
        if abs(mean_diff) < 1e-12:
            t_stat = 0.0
            p_value = 1.0
        else:
            t_stat = float(np.sign(mean_diff) * 1e9)
            p_value = 0.0
    else:
        t_stat = float(mean_diff / se_diff)
        # Hai phía (Two-tailed)
        p_value = float(2.0 * (1.0 - stats.t.cdf(np.abs(t_stat), df=df)))

    # Khoảng tin cậy cho độ chênh lệch trung bình
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df))
    ci_diff_lower = mean_diff - t_crit * se_diff
    ci_diff_upper = mean_diff + t_crit * se_diff

    # Xác định kết luận
    is_significant = p_value < alpha
    if is_significant:
        if mean_diff < 0:
            verdict = f"{model_name}_SIGNIFICANTLY_SUPERIOR"
            verdict_text = f"Mô hình {model_name} vượt trội hơn {baseline_name} có ý nghĩa thống kê (p < {alpha})."
        else:
            verdict = f"{baseline_name}_SIGNIFICANTLY_SUPERIOR"
            verdict_text = f"{baseline_name} vượt trội hơn {model_name} có ý nghĩa thống kê (p < {alpha})."
    else:
        verdict = "NO_STATISTICAL_DIFFERENCE"
        verdict_text = f"Không có sự khác biệt có ý nghĩa thống kê giữa {model_name} và {baseline_name} (p = {p_value:.4f} >= {alpha})."

    return {
        "model_name": model_name,
        "baseline_name": baseline_name,
        "days": days_list,
        "n_days": n,
        "daily_differences": [round(float(d), 4) for d in diffs],
        "mean_difference": round(mean_diff, 4),
        "std_difference": round(std_diff, 4),
        "se_difference": round(se_diff, 4),
        "t_statistic": round(t_stat, 4),
        "degrees_of_freedom": df,
        "p_value": round(p_value, 6),
        "alpha": alpha,
        "is_significant": is_significant,
        "diff_ci_95": [round(ci_diff_lower, 4), round(ci_diff_upper, 4)],
        "verdict": verdict,
        "verdict_text": verdict_text,
    }


def spatial_cluster_bootstrap(
    data_df: pd.DataFrame,
    metric_calculator: Callable[[pd.DataFrame], float],
    cluster_col: str = "road_name",
    n_boot: int = 1000,
    alpha: float = 0.05,
    random_seed: int = 42,
) -> Dict[str, Any]:
    r"""
    Spatial Cluster Bootstrap: Tái lấy mẫu có hoàn lại ở cấp độ cụm hành lang (Corridor Clusters),
    bảo toàn tính tự tương quan không gian (Spatial Autocorrelation) của mạng lưới đường đô thị.

    Quy trình:
      1. Xác định danh sách các cụm hành lang độc lập C = {c_1, c_2, ..., c_M}.
      2. Với mỗi lượt bootstrap b in {1, ..., B}:
         - Bốc ngẫu nhiên có hoàn lại M cụm từ C -> C^*_b.
         - Trích xuất toàn bộ bản ghi thuộc các cụm trong C^*_b -> Sub-DataFrame D^*_b.
         - Tính giá trị chỉ số: \theta^*_b = \text{metric\_calculator}(D^*_b).
      3. Ước lượng khoảng tin cậy phân vị thực nghiệm [q_{\alpha/2}, q_{1 - \alpha/2}].

    Args:
        data_df: DataFrame chứa dữ liệu quan trắc và mô phỏng trên từng cạnh.
        metric_calculator: Hàm nhận vào DataFrame con và trả về một số thực (ví dụ RMSE, Spearman rho...).
        cluster_col: Tên cột gom cụm không gian (mặc định 'road_name' hoặc 'corridor_cluster').
        n_boot: Số lượt bootstrap (mặc định 1000).
        alpha: Mức ý nghĩa (0.05).
        random_seed: Hạt giống ngẫu nhiên để tái lặp kết quả.

    Returns:
        Dict chứa thống kê bootstrap: original_metric, boot_mean, boot_std (SE), CI lower/upper.
    """
    if cluster_col not in data_df.columns:
        raise KeyError(f"Không tìm thấy cột gom cụm không gian '{cluster_col}' trong DataFrame!")

    unique_clusters = np.array(data_df[cluster_col].unique())
    n_clusters = len(unique_clusters)

    if n_clusters < 3:
        raise ValueError(f"Cần ít nhất 3 cụm không gian để thực hiện Spatial Cluster Bootstrap (hiện có {n_clusters})!")

    # Tính chỉ số trên toàn bộ dữ liệu gốc
    original_val = float(metric_calculator(data_df))

    # Tách trước dữ liệu theo cụm để tăng tốc độ lặp
    cluster_groups = {c: group for c, group in data_df.groupby(cluster_col)}

    rng = np.random.default_rng(random_seed)
    boot_estimates = np.empty(n_boot, dtype=float)

    for b in range(n_boot):
        # Bốc M cụm có hoàn lại
        sampled_clusters = rng.choice(unique_clusters, size=n_clusters, replace=True)
        # Gộp các DataFrame của cụm được chọn
        sampled_dfs = [cluster_groups[c] for c in sampled_clusters]
        boot_sample_df = pd.concat(sampled_dfs, ignore_index=True)
        boot_estimates[b] = float(metric_calculator(boot_sample_df))

    boot_mean = float(np.mean(boot_estimates))
    boot_std = float(np.std(boot_estimates, ddof=1))
    bias = float(boot_mean - original_val)

    # Phân vị thực nghiệm (Percentile Bootstrap)
    ci_lower = float(np.percentile(boot_estimates, 100.0 * (alpha / 2.0)))
    ci_upper = float(np.percentile(boot_estimates, 100.0 * (1.0 - alpha / 2.0)))

    return {
        "cluster_col": cluster_col,
        "n_clusters": n_clusters,
        "n_bootstrap": n_boot,
        "original_metric": round(original_val, 4),
        "bootstrap_mean": round(boot_mean, 4),
        "bootstrap_se": round(boot_std, 4),
        "bootstrap_bias": round(bias, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "confidence_level": round((1.0 - alpha) * 100, 1),
        "ci_formatted": f"[{ci_lower:.3f}, {ci_upper:.3f}]",
        "academic_report": f"{original_val:.3f} (95% Cluster Boot CI: [{ci_lower:.3f}, {ci_upper:.3f}], M={n_clusters} corridors)",
    }


# ==============================================================================
# TỰ KIỂM THỬ ĐỘC LẬP (SELF-TEST SUITE)
# ==============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("[*] KIỂM THỬ TỰ THÂN: statistical_tester.py (CHUẨN HỌC THUẬT IEEE/TRB)")
    print("=" * 70)

    # 1. Kiểm thử Two-Tier Hierarchical Inference
    print("\n--- 1. Kiểm thử Two-Tier Hierarchical Inference (5 Demand x 4 Sim Seeds) ---")
    np.random.seed(42)
    sample_records = []
    # 5 demand seeds, mỗi demand seed có 4 sim seeds
    base_demands = [3.8, 4.1, 3.9, 4.3, 4.0]
    for d_idx, d_val in enumerate(base_demands, 1):
        for s_idx in range(1, 5):
            sim_noise = np.random.normal(0, 0.15)
            sample_records.append({
                "demand_seed": f"Demand_S{d_idx}",
                "sim_seed": f"Sim_{s_idx}",
                "rmse": d_val + sim_noise,
            })
    df_runs = pd.DataFrame(sample_records)

    res_hier = hierarchical_two_tier_ci(df_runs, metric_col="rmse", alpha=0.05)
    print(f"[+] Số Demand Seeds: {res_hier['num_demand_seeds']}")
    print(f"[+] Bậc tự do (df):   {res_hier['degrees_of_freedom']} (Bắt buộc phải là 4, không phải 19)")
    print(f"[+] t_critical:       {res_hier['t_critical']} (Hệ số tới hạn t_0.975,4 = 2.776)")
    print(f"[+] Kết quả báo cáo:  {res_hier['academic_report']}")

    assert res_hier["degrees_of_freedom"] == 4, "Lỗi: df phải bằng 4!"
    assert abs(res_hier["t_critical"] - 2.7764) < 0.001, "Lỗi: t_crit không khớp phân phối t!"

    # 2. Kiểm thử LODO Paired t-Test
    print("\n--- 2. Kiểm thử LODO Paired t-Test (So sánh SUMO vs Median qua 5 ngày) ---")
    # Giả lập 5 ngày kiểm định ngoại suy với phương sai thực tế
    days_data_sumo = {"Day_1": 4.10, "Day_2": 3.82, "Day_3": 4.28, "Day_4": 3.91, "Day_5": 4.04}
    days_data_base = {"Day_1": 4.45, "Day_2": 4.22, "Day_3": 4.65, "Day_4": 4.31, "Day_5": 4.42}

    res_lodo = lodo_paired_test(days_data_sumo, days_data_base, model_name="SUMO", baseline_name="Median")
    print(f"[+] Số ngày đối chuẩn:   {res_lodo['n_days']}")
    print(f"[+] Chênh lệch trung bình: {res_lodo['mean_difference']} km/h")
    print(f"[+] t-statistic:          {res_lodo['t_statistic']}")
    print(f"[+] p-value:              {res_lodo['p_value']}")
    print(f"[+] Phán quyết:           {res_lodo['verdict']}")
    print(f"[+] Kết luận:             {res_lodo['verdict_text']}")

    assert res_lodo["is_significant"] is True, "Lỗi: SUMO phải vượt trội hơn Median có ý nghĩa!"
    assert res_lodo["verdict"] == "SUMO_SIGNIFICANTLY_SUPERIOR"

    # 3. Kiểm thử Spatial Cluster Bootstrap theo Hành lang
    print("\n--- 3. Kiểm thử Spatial Cluster Bootstrap theo Hành lang Tuyến đường ---")
    corridors = ["Pasteur", "Nam Kỳ Khởi Nghĩa", "Hai Bà Trưng", "Nguyễn Thị Minh Khai", "Võ Văn Tần", "Điện Biên Phủ"]
    boot_rows = []
    for c in corridors:
        # Mỗi hành lang có 10 đoạn đường
        for i in range(10):
            v_obs = np.random.uniform(15, 35)
            v_sim = v_obs + np.random.normal(0, 2.0)
            boot_rows.append({
                "edge_id": f"{c}_seg_{i}",
                "road_name": c,
                "v_obs": v_obs,
                "v_sim": v_sim,
            })
    df_spatial = pd.DataFrame(boot_rows)

    def calc_rmse(sub_df: pd.DataFrame) -> float:
        return float(np.sqrt(np.mean((sub_df["v_sim"] - sub_df["v_obs"]) ** 2)))

    res_boot = spatial_cluster_bootstrap(
        df_spatial,
        metric_calculator=calc_rmse,
        cluster_col="road_name",
        n_boot=500,
        random_seed=42
    )
    print(f"[+] Số cụm hành lang M:   {res_boot['n_clusters']}")
    print(f"[+] RMSE mẫu gốc:         {res_boot['original_metric']} km/h")
    print(f"[+] Bootstrap SE:         {res_boot['bootstrap_se']} km/h")
    print(f"[+] Khoảng tin cậy 95%:   {res_boot['ci_formatted']}")
    print(f"[+] Kết quả báo cáo:      {res_boot['academic_report']}")

    print("\n" + "=" * 70)
    print("[OK] statistical_tester.py HOẠT ĐỘNG HOÀN TOÀN CHUẨN XÁC THEO LÝ THUYẾT!")
    print("=" * 70)
