# Báo cáo Thí nghiệm Hiệu chuẩn & Kiểm chuẩn LODO Thử nghiệm (Pilot LODO Experiment)
**Dự án:** MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh  
**Mục tiêu:** Thử nghiệm kịch bản lưu lượng cao điểm thực tế, nhu cầu hỗn hợp 2 luồng (Composite Demand) và cơ chế gắn thẻ đoàn xe (Peak Cohort Tagging).  
**Ngày thực hiện:** 09/11/2026  
**Tham chiếu phương pháp luận:** `macro_traffic_crawler/docs/SD_EVALUATION.md` & `ROADMAP_50DAYS.md`

---

## I. Mục tiêu & Triết lý Thí nghiệm (Philosophy & Objectives)

### 1. Triết lý Thực nghiệm: Chân thực Vật lý hơn Làm đẹp Số liệu (Physical Fidelity over Metric Gaming)
Thí nghiệm này được thiết kế để khắc phục triệt để hiện tượng "Metric Gaming" (cố tình giữ tải xe ở mức non tải $\lambda \approx 1.5$ để lấy các chỉ số $CR = 98\%$ hoặc né phạt bình phương của RMSE). Thay vào đó, kịch bản tập trung vào:
- **Tái hiện đúng áp lực giờ cao điểm thực tế của TP.HCM:** Nâng mức nạp mạng lên vùng $\lambda \approx 2.0 - 3.4\text{ veh/s}$ ($7.200 - 12.240\text{ xe/h}$).
- **Bảo toàn tính liên tục của dòng xe (Non-stationary Continuous Flow):** Không ngắt tải đột ngột lúc kết thúc cao điểm.
- **Phản ánh đúng cơ cấu luồng xe nội quận vs xuyên tâm:** Tránh việc ép mọi xe phải chạy lộ trình xuyên suốt 3–4km qua toàn bộ Quận 1.

---

## II. Ước lượng Chi phí Tính toán (Computational Cost Estimation)

Khi mở rộng không gian tìm kiếm tự do cho cả 7 lát cắt $\lambda_t \in [0.50, \; 4.00]\text{ veh/s}$:

| Đại lượng | Giá trị thiết kế | Giải thích kỹ thuật |
| :--- | :---: | :--- |
| **Số chiều bài toán ($D$)** | $7$ | 7 lát cắt 30 phút từ 06:30 đến 10:00 |
| **Kích thước quần thể ($\lambda_{\text{cma}}$)** | $9$ | Công thức chuẩn Hansen: $\lambda = 4 + \lfloor 3 \ln(D) \rfloor = 4 + \lfloor 3 \ln(7) \rfloor = 9$ |
| **Số thế hệ tối đa ($G_{\max}$)** | $10 - 15$ | Đủ để ma trận hiệp phương sai của CMA-ES hội tụ |
| **Tổng số lượt mô phỏng (Trials)** | $90 - 135$ | $9 \times 10 = 90$ hoặc $9 \times 15 = 135$ lần chạy ngầm |
| **Thời gian chạy 1 lượt SUMO** | $\approx 65 - 80\text{s}$ | Chạy 3.5 giờ với Sublane 0.25m, step-length 0.2s |
| **Song song hóa đa tiến trình** | $3$ workers | Tận dụng CPU đa nhân, lưu trạng thái vào SQLite `cmaes_study.db` |
| **Tổng thời gian ước lượng** | **$\approx 35 - 55$ phút** | $30 - 45$ đợt tuần tự $\times 75\text{s} \approx 2.250 - 3.375\text{s}$ |

> **Đánh giá:** Chi phí tính toán hoàn toàn nằm trong tầm kiểm soát của máy trạm cá nhân, không gây quá tải và có thể ngắt/chạy tiếp (checkpointing) an toàn nhờ cơ sở dữ liệu Optuna SQLite.

---

## III. Cấu hình Tham số Thực nghiệm Chi tiết (Experiment Configurations)

### 1. Cơ chế Nhu cầu Hỗn hợp (Composite Demand Model)
Thay vì dùng một luồng ngẫu nhiên duy nhất, kịch bản phân tách thành 2 luồng độc lập:
* **Luồng 1 (Through Traffic - 60% lưu lượng):**
  - Đại diện cho dòng xe từ các quận lân cận (Bình Thạnh, Phú Nhuận, Quận 3, Quận 4) đi xuyên tâm qua Quận 1.
  - Cự ly hành trình: $\ge 1.200\text{ m}$ (`--min-distance 1200`).
  - Hệ số biên: `--fringe-factor 5.0` (ưu tiên xuất phát từ cổng biên mạng lưới).
* **Luồng 2 (Local Circulation - 40% lưu lượng):**
  - Đại diện cho các chuyến đi nội quận (đi chợ, ăn sáng, giao dịch công vụ, đi làm cự ly ngắn).
  - Cự ly hành trình: $800\text{ m} - 1.800\text{ m}$ (`--min-distance 800 --max-distance 1800`).
  - Hệ số biên: `--fringe-factor 1.0` (phân bố đều trong lòng mạng lưới).

### 2. Chu kỳ Đèn Tín hiệu
* Duy trì **Chu kỳ cố định 90s** (Pha xanh 40s / Vàng 5s / Xanh 40s / Vàng 5s) theo quy chuẩn TCVN 13592:2022 và công thức Webster.

### 3. Vector Tiên nghiệm Thực tế Cao điểm (Realistic Peak Prior)
Vector tiên nghiệm $\boldsymbol{\lambda}_{\text{prior}}$ được cấu hình trực tiếp:
$$\boldsymbol{\lambda}_{\text{prior}} = [2.00, \; 2.60, \; 3.20, \; 3.40, \; 3.00, \; 2.70, \; 2.50]\text{ veh/s}$$
- `06:30 - 07:00`: $2.00\text{ veh/s}$ ($7.200\text{ xe/h}$) - Đầu giờ cao điểm.
- `07:00 - 07:30`: $2.60\text{ veh/s}$ ($9.360\text{ xe/h}$) - Dòng xe tăng mạnh.
- `07:30 - 08:30`: $3.20 - 3.40\text{ veh/s}$ ($11.520 - 12.240\text{ xe/h}$) - Đỉnh kẹt xe.
- `08:30 - 09:30`: $2.70 - 3.00\text{ veh/s}$ ($9.720 - 10.800\text{ xe/h}$) - Duy trì mức đông theo dữ liệu TomTom.
- `09:30 - 10:00`: $2.50\text{ veh/s}$ ($9.000\text{ xe/h}$) - Hạ nhiệt dần.

### 4. Cơ chế Gắn thẻ Đoàn xe Cao điểm (Peak Cohort Tagging)
- Theo dõi riêng đoàn xe xuất phát trong khung giờ cao điểm trọng tâm: $t \in [3.600\text{s}, \; 10.800\text{s}]$ (07:00 – 09:00).
- Nhóm xe này tiếp tục hoàn thành hành trình trên nền dòng xe bình thường sau 09:00 để đo chính xác tỷ lệ hoàn thành $CR\%$ và độ trễ $\bar{T}_{\text{loss}}$ thực tế.

---

## IV. Kiểm thử Cú pháp Đường ống (Surrogate Dry-Run Sanity Check) & Cảnh báo Liêm chính Học thuật

> [!CAUTION] CẢNH BÁO LIÊM CHÍNH HỌC THUẬT (DATA LEAKAGE & SURROGATE WARNING)
> Các chỉ số trong bảng dưới đây thu được từ **Chế độ Kiểm thử Cú pháp (Surrogate Dry-Run với cờ `--dry-run`)**, sử dụng ma trận trung vị lịch sử 5 ngày của TomTom để kiểm tra khả năng thực thi toán học của các tiêu chí Wasserstein, Spearman và Skill Score.
> **TUYỆT ĐỐI KHÔNG SỬ DỤNG SỐ LIỆU NÀY LÀM KẾT QUẢ ĐỐI CHUẨN KHOA HỌC CHO BÀI BÁO HOẶC KHÓA LUẬN!**  
> Kết quả mô phỏng vi mô SUMO thực tế (Full Microsimulation với cờ `--sim`) sẽ có mức sai số cao hơn nhiều do các hạn chế vật lý tự nhiên của chu kỳ đèn cố định Fixed-Time 90s khi xe máy bị kẹt cục bộ.

### 1. Bảng Chỉ số Kiểm thử Cú pháp (Dry-Run Sanity Metrics)

| Nhóm Chỉ số | Tên Chỉ số | Giá trị Đo được (Dry-Run) | Ngưỡng Chuẩn Khoa học | Đánh giá Kỹ thuật |
| :--- | :--- | :---: | :---: | :---: |
| **Sai số Vận tốc (Error Dynamics)** | **RMSE toàn mạng** | **$1.07\text{ km/h}$** | $< 13.0\text{ km/h}$ | [Kiểm thử Cú pháp Đạt] |
| | **MAE toàn mạng** | **$0.81\text{ km/h}$** | $< 10.0\text{ km/h}$ | [Kiểm thử Cú pháp Đạt] |
| | **Max \|Bias\| theo lát cắt** | **$1.02\text{ km/h}$** | $\le 2.0\text{ km/h}$ | [Kiểm thử Cú pháp Đạt] |
| **Tương quan Thứ bậc (Rank)** | **Spearman $\rho_{\text{corridor}}$** | **$0.99$** | $\ge 0.50$ | [Kiểm thử Cú pháp Đạt] |
| **Đồng dạng Phân bố (Distribution)** | **Khoảng cách Wasserstein $W_1$** | **$0.64\text{ km/h}$** | Giảm $\ge 25\%$ | [Kiểm thử Cú pháp Đạt] |
| **Chỉ số Kỹ năng (Skill Score)** | **Skill Score so với $v_0$** | **$0.9194$** | $> 0.0$ | [Kiểm thử Cú pháp Đạt] |
| **Động học Mạng lưới (Network)** | **Tỷ lệ Hoàn thành (TCR)** | **$94.12\%$** *(gán thử nghiệm)* | $\ge 90.0\%$ | [Kiểm thử Cú pháp Đạt] |
| | **Tỷ lệ Teleport (Gridlock)** | **$0.00\%$** *(gán thử nghiệm)* | $< 0.10\%$ | [Kiểm thử Cú pháp Đạt] |

---

## V. Phân tích Hiện tượng Bùng nổ Chi phí Tính toán & Cơ chế Khắc phục

### 1. Hiện tượng Bùng nổ CPU trong Mô phỏng Vi mô Sublane:
Khi kích hoạt mô phỏng vi mô toàn phần (`--sim`) với `step-length = 0.2s` và `lateral-resolution = 0.25m`:
- Tại giây thứ $3.153\text{s}$ (khoảng 07:22 sáng), trên mạng lưới có $767$ phương tiện đang chạy và $168$ phương tiện dừng chờ.
- Thời gian tính toán mỗi bước nhảy vọt lên $44\text{ms}$ CPU time.
- Để chạy đủ $12.600\text{s}$ mô phỏng, thời gian thực tế CPU ngốn hơn **35 - 45 phút cho 1 trial duy nhất**!
- Điều này khiến bài toán tối ưu 90 trials CMA-ES bùng nổ lên **hơn 17 giờ tính toán**, không khả thi trên thực tế.

### 2. Giải pháp Cân đối Kỹ thuật (Pragmatic Engineering Solutions):
- **Điều chỉnh Tham số Vi mô Khả thi:**
  - Chuyển `step-length` từ $0.2\text{s} \to 0.4\text{s}$ (giảm 50% số bước mô phỏng từ 63.000 xuống 31.500).
  - Chuyển `lateral-resolution` từ $0.25\text{m} \to 0.40\text{m}$ (giảm 60% số cell quét va chạm ngang mà vẫn bảo đảm độ rộng xe máy 0.8m theo TCVN 104:2007).
  - Tích hợp cơ chế **Watchdog Timeout** (`timeout_sec = 600s`) trong `evaluate_candidate` để tự động ngắt nếu mạng lưới bị khóa cứng (Deadlock).
- **Rào chắn Liêm chính Học thuật Tự động:**
  - Mã nguồn `lodo_cross_validator.py` đã bị khóa cứng, bắt buộc người dùng chọn rõ `--sim`, `--sim-artifact` hoặc `--dry-run`.
  - Tệp nghiệm thu chính thức `level1_lodo_results.json` bị cấm ghi đè từ chế độ Dry-Run.
  - Tích hợp Skill rà soát liêm chính học thuật: `.agents/skills/academic-simulation-audit/SKILL.md`.

