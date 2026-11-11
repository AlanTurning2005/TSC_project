---
name: academic-simulation-audit
description: >-
  Audits, verifies, and enforces academic integrity and physical fidelity for traffic simulation experiments.
  Detects and prevents surrogate data leakage, hardcoded telemetry, metric gaming, and computational explosion risks in SUMO and MARL-TSC pipelines.
---

# Quy trình Rà soát Liêm chính Học thuật & Mô phỏng Giao thông (Academic Simulation Audit)

Kỹ năng này cung cấp quy chuẩn rà soát tự động và bắt buộc dành cho Agent trước khi thực thi, tối ưu hóa hoặc báo cáo kết quả từ các mô hình mô phỏng giao thông (SUMO, CityFlow) và Học tăng cường Đa tác tử (MARL-TSC).

---

## 1. Mục tiêu Cốt lõi & Nguyên tắc Cấm kỵ (Non-Negotiable Principles)

Mục tiêu cao nhất của nghiên cứu là **Chân thực Vật lý (Physical Fidelity) hơn Làm đẹp Số liệu (Metric Gaming)**.

### 4 "Vùng Đỏ" Tuyệt đối Nghiêm cấm:
1. **Cấm Leakage qua Mô hình Surrogate:** Không bao giờ dùng `v_historical_median` hoặc `v_obs` cộng trừ độ lệch/nhiễu để giả vờ làm ma trận mô phỏng $v_{\text{sim}}$.
2. **Cấm Hardcode Telemetry:** Không bao giờ gán cứng các chỉ số $TCR$, $\text{teleport\_rate}$, $\bar{T}_{\text{loss}}$ trong code đánh giá.
3. **Cấm Xuất Dry-run thành Benchmark Chính thức:** Kết quả từ các bài test cú pháp code không bao giờ được ghi đè vào tệp nghiệm thu chính thức (`level1_lodo_results.json`).
4. **Cấm Giấu Bùng nổ Tính toán:** Khi mô phỏng với Sublane Model xe máy, phải tính toán chi phí thực tế và áp dụng cơ chế timeout/watchdog thay vì để tiến trình treo ngầm hàng chục giờ.

---

## 2. Checklist 5 Bước Rà soát Liêm chính trước khi Báo cáo

Mỗi khi Agent chạy hoặc trình bày kết quả từ mô phỏng, BẮT BUỘC thực hiện kiểm tra chéo:

### Bước 1: Chứng thực Nguồn gốc Dữ liệu Mô phỏng (Trace Provenance Audit)
- Tệp `edgedata.xml` và `summary.xml` (hoặc `tripinfo.xml`) có thực sự được sinh ra từ lệnh gọi SUMO nhị phân trong lượt chạy hiện tại không?
- Kiểm tra kích thước tệp: Tệp kết quả SUMO phải lớn hơn 0 bytes và khớp với timestamp của thời điểm thực thi.
- Nếu không có tệp trace thực tế, BẮT BUỘC gắn nhãn: `[GIẢ ĐỊNH / CHƯA CHẠY THỰC NGHIỆM]`.

### Bước 2: Rà soát Gán cứng Chỉ số (Hardcode Grep Audit)
- Quét mã nguồn đánh giá: Có xuất hiện các phép gán tĩnh như `{"tcr": 0.94, "teleport_rate": 0.0}` không?
- Mọi chỉ số TCR phải được tính bằng: $\text{arrived} / \max(1, \text{inserted})$.
- Mọi chỉ số Teleport phải được tính bằng: $\text{teleports} / \max(1, \text{inserted})$.

### Bước 3: Rà soát Tính Khả thi Vật lý (Physical Reality Check)
- **Dưới chu kỳ đèn cố định (Fixed-Time 90s) ở Quận 1:**
  - Nếu báo cáo $RMSE < 3.0\text{ km/h}$ trên 66 nút giao: **CẢNH BÁO ĐỎ - BẤT THƯỜNG VẬT LÝ.** Với dòng xe máy cao điểm, xung đột rẽ trái và nghẽn cục bộ luôn tạo ra độ phân tán sai số $\text{Var}(e) \ge 12\text{ km/h}$.
  - Nếu báo cáo $\text{TCR} = 100\%$ và Teleport = 0% ở mức tải $\lambda \ge 3.0\text{ veh/s}$: **CẢNH BÁO ĐỎ - LÀM ĐẸP SỐ LIỆU.** Mạng lưới Quận 1 trong giờ cao điểm chắc chắn có tỷ lệ xe trễ và dừng chờ.

### Bước 4: Kiểm soát Tài nguyên & Bùng nổ Tính toán (Computational Scalability Audit)
- **Tham số cấu hình Sublane:**
  - `step-length`: Đặt ở mức $0.4\text{s}$ (không đặt $0.1 - 0.2\text{s}$ trừ khi có mục đích khảo sát vi mô cực ngắn).
  - `lateral-resolution`: Đặt ở mức $0.40\text{m}$ (đáp ứng đúng bề rộng $0.8\text{m}$ của xe máy Việt Nam theo TCVN 104:2007).
  - Cơ chế Timeout: Mỗi trial SUMO trong Optuna CMA-ES phải có giới hạn ngắt `timeout=600s` (10 phút) để tránh nghẽn deadlock.

### Bước 5: Phân định Nhãn Báo cáo (Reporting Transparency)
- Mọi kết quả trình bày cho người dùng phải có bảng thông tin nguồn gốc (Provenance Table):
  - Phương thức: `Mô phỏng SUMO Vi mô Thực tế` hay `Surrogate Dry-run`.
  - Tham số vi mô: Step-length, Lateral-resolution, Seed, Tổng số xe đã nạp.
  - Tệp lưu trữ kết quả và mã kiểm định chéo.
