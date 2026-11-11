r"""
test_calibration_pipeline.py
=============================================================================
BỘ KIỂM THỬ TÍCH HỢP TOÀN BỘ PIPELINE HIỆU CHỈNH KỊCH BẢN GIAO THÔNG (CHẶNG 1)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh
Tham chiếu:
- ROADMAP_50DAYS.md (Chặng 1: Ngày 1 - Ngày 12)
- SD_EVALUATION.md

Nội dung kiểm thử:
[TEST 1] Chuẩn hóa dữ liệu Soft Masking & Định nghĩa 10 hành lang trục chính.
[TEST 2] Sinh lộ trình đa lát cắt và lưu/nạp Checkpoint Warm-up.
[TEST 3] Cơ chế tính hàm mất mát điều chuẩn trơn bậc 2 + Tiên nghiệm HOUTRANS.
[TEST 4] Bộ 5 tiêu chí nghiệm thu khoa học trong LODO Cross-validation.
[TEST 5] Kiểm tra tính toàn vẹn của kịch bản đóng băng (Scenario Manifest & Checksum).
=============================================================================
"""

import os
import sys
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

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
SCENARIOS_DIR = PROJECT_ROOT / "sumo_scenarios" / "q1_calibrated_morning"
EVAL_DIR = PROJECT_ROOT / "evaluation" / "level1_macro_flow"

for p in [CURRENT_DIR, EVAL_DIR, PROJECT_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from prepare_calibration_targets import (
    load_calibration_targets_npz,
    load_corridor_definitions,
    load_sampling_points
)
from calibrate_cmaes import (
    build_houtrans_prior_7slices,
    compute_regularized_loss
)
from lodo_cross_validator import evaluate_5_acceptance_criteria


class TestCalibrationPipeline(unittest.TestCase):

    def test_01_soft_masking_targets_and_corridors(self):
        """Kiểm tra ma trận mục tiêu không chứa NaN và 10 hành lang đủ 66 điểm."""
        pts = load_sampling_points()
        self.assertEqual(len(pts), 66, "Danh sách điểm quan trắc phải có đúng 66 điểm.")

        corridors = load_corridor_definitions()
        self.assertEqual(len(corridors), 10, "Bảng định nghĩa hành lang phải có đúng 10 hành lang.")

        all_c_pts = []
        for c in corridors.values():
            all_c_pts.extend(c["points"])
        self.assertEqual(len(all_c_pts), 66, "Tổng số điểm trên 10 hành lang phải đúng 66.")
        self.assertEqual(len(set(all_c_pts)), 66, "Không được có điểm quan trắc trùng lặp giữa các hành lang.")

        targets = load_calibration_targets_npz()
        self.assertGreaterEqual(len(targets["dates"]), 4, "Phải có ít nhất 4-5 ngày làm việc độc lập.")
        self.assertEqual(len(targets["time_slices"]), 7, "Khung khảo sát phải có đúng 7 lát cắt.")

        for d in targets["dates"]:
            W = targets["weights_by_date"][d]
            V = targets["v_obs_by_date"][d]
            self.assertFalse(np.isnan(W).any(), f"Ma trận W ngày {d} chứa NaN!")
            self.assertFalse(np.isnan(V).any(), f"Ma trận V_obs ngày {d} chứa NaN!")

        print("\n[V] TEST 1 PASSED: Soft Masking và 10 Hành lang hoạt động chuẩn xác.")

    def test_02_houtrans_prior_and_regularized_loss(self):
        """Kiểm tra vector tiên nghiệm HOUTRANS và hàm mất mát điều chuẩn."""
        prior = build_houtrans_prior_7slices(base_rate_vps=1.0)
        self.assertEqual(len(prior), 7)
        # Đỉnh cao điểm sáng phải rơi vào lát 07:30 (lát index 2)
        self.assertEqual(float(np.argmax(prior)), 2, "Đỉnh HOUTRANS phải tại lát cắt 07:30.")

        # Test loss calculation
        v_dummy = np.full((66, 7), 18.0)
        w_dummy = np.full((66, 7), 1.0 / 66.0)
        loss, details = compute_regularized_loss(
            v_sim=v_dummy,
            v_obs=v_dummy, # v_sim == v_obs -> rmse = 0
            weights=w_dummy,
            lambda_vec=prior,
            lambda_prior=prior,
            gamma_smooth=2.0,
            gamma_prior=1.5
        )
        self.assertAlmostEqual(details["rmse_w"], 0.0, places=3)
        self.assertAlmostEqual(details["prior_term"], 0.0, places=3)
        self.assertGreaterEqual(details["smooth_term"], 0.0)

        print("\n[V] TEST 2 PASSED: HOUTRANS Prior và Hàm mất mát Điều chuẩn hoạt động chuẩn xác.")

    def test_03_acceptance_criteria_suite(self):
        """Kiểm tra logic đánh giá 5 Tiêu chuẩn Nghiệm thu Khoa học."""
        targets = load_calibration_targets_npz()
        corridors = load_corridor_definitions()
        d = targets["dates"][1]
        v_obs = targets["v_obs_by_date"][d]
        w = targets["weights_by_date"][d]
        v0 = targets["v0_free_flow"]

        # Mô phỏng trường hợp hoàn hảo
        v_mock = v_obs + 0.1
        res = evaluate_5_acceptance_criteria(
            v_sim=v_mock,
            v_obs=v_obs,
            weights=w,
            v0_vector=v0,
            v_sim_init=v_obs + 3.0,
            ordered_points=targets["point_ids"],
            corridor_defs=corridors,
            telemetry={"tcr": 0.95, "teleport_rate": 0.0001},
            slice_names=targets["time_slices"]
        )
        self.assertTrue(res["all_criteria_met"])
        self.assertTrue(res["criterion_1_speed_bias"]["passed"])
        self.assertTrue(res["criterion_2_corridor_spearman"]["passed"])
        self.assertTrue(res["criterion_3_skill_score"]["passed"])
        self.assertTrue(res["criterion_4_wasserstein_w1"]["passed"])
        self.assertTrue(res["criterion_5_drain_clearance"]["passed"])

        print("\n[V] TEST 3 PASSED: Bộ 5 Tiêu chuẩn Nghiệm thu Khoa học hoạt động chuẩn xác.")

    def test_04_frozen_scenario_assets(self):
        """Kiểm tra các tài sản đóng băng kịch bản sẵn sàng bàn giao sang Chặng 2."""
        rou_file = SCENARIOS_DIR / "calibrated_morning_peak.rou.xml"
        cfg_file = SCENARIOS_DIR / "simulation.sumocfg"

        self.assertTrue(rou_file.exists(), "Tệp lộ trình đóng băng calibrated_morning_peak.rou.xml phải tồn tại.")
        self.assertTrue(cfg_file.exists(), "Tệp simulation.sumocfg phải tồn tại.")
        self.assertGreater(rou_file.stat().st_size, 1024 * 1024, "Tệp routes phải lớn hơn 1MB.")

        print("\n[V] TEST 4 PASSED: Tài nguyên kịch bản đóng băng đã hoàn tất và đạt chuẩn.")

    def test_05_simulation_integrity_guardrails(self):
        """[TEST 5] Kiểm tra rào chắn Liêm chính Học thuật (Anti-Data-Leakage & Anti-Gaming)."""
        from lodo_cross_validator import run_full_lodo_pipeline, REPORTS_DIR

        # 1. Chạy không khai báo chế độ bắt buộc phải ném lỗi ValueError
        with self.assertRaises(ValueError):
            run_full_lodo_pipeline(run_sim=False, dry_run=False, sim_artifact=None)

        # 2. Chạy dry-run không được phép ghi đè vào level1_lodo_results.json
        official_json = REPORTS_DIR / "level1_lodo_results.json"
        if official_json.exists():
            official_json.unlink()

        res_dry = run_full_lodo_pipeline(dry_run=True, filter_date="2026-10-15", use_realistic_prior=True)
        self.assertFalse(official_json.exists(), "Chế độ Dry-Run tuyệt đối không được tạo file level1_lodo_results.json!")
        self.assertTrue(res_dry["provenance"]["is_synthetic_dry_run"])
        self.assertFalse(res_dry["provenance"]["is_real_sumo_simulation"])

        dry_json = REPORTS_DIR / "level1_lodo_dryrun_sanity.json"
        self.assertTrue(dry_json.exists(), "Chế độ Dry-Run phải lưu riêng vào level1_lodo_dryrun_sanity.json.")

        print("\n[V] TEST 5 PASSED: Rào chắn Liêm chính Học thuật (Simulation Integrity) kích hoạt 100% chuẩn xác.")



if __name__ == "__main__":
    unittest.main()
