# KẾ HOẠCH HÀNH ĐỘNG TRIỂN KHAI ĐỀ TÀI MARL-TSC (50 NGÀY)
## (HCMC Speed-Calibrated Heterogeneous Sublane Testbed & Multi-Agent Reinforcement Learning Control)

---

### TỔNG QUAN LỘ TRÌNH 4 CHẶNG (50 NGÀY)

```
[CHẶNG 1: NGÀY 1 - 12] ──► [CHẶNG 2: NGÀY 13 - 22] ──► [CHẶNG 3: NGÀY 23 - 38] ──► [CHẶNG 4: NGÀY 39 - 50]
  Hiệu chuẩn Nhu cầu λ(t)     Adapter SUMO-RL, Baseline    Huấn luyện MARL 5 Seeds     Phân tích Thực nghiệm,
  qua CMA-ES & Khóa Kịch bản    & Sub-network Smoke Test     & Stress-test Quá tải        Viết Luận văn & Paper
  (Soạn sẵn Chương 2 & 3)       (Soạn sẵn Phương pháp luận)  (Báo cáo IQM + Bootstrap)    (3 Ngày Buffer Đệm)
```

#### Bảng Thông số Kỹ thuật & Môi trường Thống nhất Toàn Dự án

| Tham số / Cấu hình | Giá trị Chuẩn hóa | Đơn vị / Định dạng | Căn cứ Khoa học & Nguồn Quy chuẩn |
| :--- | :--- | :--- | :--- |
| **Mạng lưới mô phỏng** | `q1_map.net.xml` | 34 nút giao có đèn (`tlLogic`) | Trích xuất từ OSM Quận 1 & 3, biên tập qua NETEDIT |
| **Thời gian đèn vàng** | $t_{\text{yellow}} = 3.0$ | Giây (s) | QCVN 41:2019/BGTVT (chuẩn hóa trên 34 nút giao) |
| **Bước thời gian vi mô** | `--step-length 0.2` | 5 bước tích phân / giây | [HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/docs/HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md) |
| **Độ phân giải ngang** | `--lateral-resolution 0.25` | Mét (m) | Mô hình Sublane xe máy lách làn (SUMO sublane model) |
| **Cơ cấu phương tiện** | 85% Xe máy, 12% Ô tô con, 3% Xe buýt | Tỷ lệ (%) | Khảo sát HOUTRANS / JICA TP.HCM |
| **Hành vi lách làn** | `latAlignment="arbitrary"` | Thuộc tính vType | Xe máy di chuyển không phụ thuộc vạch kẻ làn |
| **Vận tốc tối đa vType** | Xe máy: 9.72 m/s (35 km/h), Ô tô: 9.72 m/s, Buýt: 8.33 m/s (30 km/h) | m/s | QCVN 41:2019/BGTVT quy định tốc độ đô thị hỗn hợp |
| **Khoảng cách ngang an toàn** | Xe máy: 0.25m, Ô tô: 0.60m, Buýt: 0.80m | Mét (m) | `minGapLat` chuẩn hóa theo bề rộng xe máy đô thị |
| **Cửa sổ Khởi động (Warm-up)** | 06:00 – 06:30 (1.800s) | Giây (s) | Nạp luồng xe tiền cao điểm, tránh mạng rỗng |
| **Cửa sổ Hiệu chuẩn Nhu cầu** | 06:30 – 10:00 (7 lát cắt $\times$ 30 phút) | Giây (s) | Vector quy mô nhu cầu $\boldsymbol{\lambda}(t) \in \mathbb{R}^7$ |
| **Cửa sổ Huấn luyện RL** | 07:00 – 09:00 (7.200s) | Giây (s) | Khung cao điểm sáng căng thẳng nhất |
| **Cửa sổ Xả mạng (Drain Phase)** | 09:00 – 09:30 (1.800s) | Giây (s) | Ngưng nạp xe mới để triệt tiêu Survivor Bias |

---

## CHẶNG 1: HIỆU CHUẨN NHU CẦU ĐỘNG HỌC $\boldsymbol{\lambda}(t)$ QUA CMA-ES & KHÓA KỊCH BẢN (NGÀY 1 – NGÀY 12)

### 1. Mục tiêu Chặng 1
* Xây dựng và nghiệm thu pipeline tối ưu hóa mô phỏng vi mô khép kín chạy ngầm (Headless Simulation-Optimization) sử dụng thuật toán tiến hóa thích ứng ma trận hiệp phương sai (**CMA-ES**), khắc phục triệt để hạn chế không thể song song hóa và tính nhạy cảm với nhiễu của Powell / Nelder-Mead.
* Thiết lập pha khởi động mạng lưới (Warm-up: 06:00 – 06:30) từ dữ liệu thực tế, loại bỏ hoàn toàn sai số mạng rỗng lúc 06:30.
* Áp dụng cơ chế lọc mềm (Soft Masking) kết hợp trọng số nghịch đảo phương sai theo độ tin cậy TomTom, loại bỏ nguy cơ mất dữ liệu/gây lỗi NaN khi lọc cứng $c \ge 0.70$.
* Tối ưu hóa vector quy mô nhu cầu nạp mạng toàn cục $\boldsymbol{\lambda}(t) \in \mathbb{R}^7$ trên khung giờ cao điểm sáng 06:30 – 10:00.
* Thu thập đủ ngày làm việc thứ 5 độc lập và hoàn tất báo cáo thống kê kiểm định chéo LODO (Leave-One-Day-Out).
* Xuất tệp lộ trình chuẩn hóa đóng băng (`calibrated_morning_peak.rou.xml`) và snapshot trạng thái khởi động (`checkpoint_warmup_0700.xml`) bàn giao sang Chặng 2.
* **Viết song song:** Soạn thảo xong bản thảo Chương 2 và Chương 3 của Khóa luận vào cuối ngày 12.

---

### 2. Bảng Kiểm kê Dữ liệu Thực tế (Data Inventory Matrix)

| Ngày Khảo sát | Thứ | Khung Giờ Cào Thực tế | Trạng thái Cao điểm Sáng (06:00 – 10:00) | Vai trò trong Phân tích | Tệp Lưu trữ Nguồn |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **14/10/2026** | Thứ Tư | 07:03 – 23:50 | Đủ từ 07:03 – 10:00 (Khuyết 06:00–07:00, nội suy warm-up từ 15/10) | Fold 1 LODO | [macro_traffic_history.csv](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/data/processed/macro_traffic_history.csv) |
| **15/10/2026** | Thứ Năm | 00:00 – 23:55 | Trọn vẹn 24h (Có đủ 06:00 – 10:00) | Fold 2 LODO (Benchmark Day) | [macro_traffic_history.csv](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/data/processed/macro_traffic_history.csv) |
| **16/10/2026** | Thứ Sáu | 00:07 – 14:41 | Trọn vẹn cao điểm sáng (Có đủ 06:00 – 10:00) | Fold 3 LODO | [macro_traffic_history.csv](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/data/processed/macro_traffic_history.csv) |
| **19/10/2026** | Thứ Hai | 07:19 – 12:28 | Đủ từ 07:19 – 10:00 (Nội suy warm-up từ 15/10) | Fold 4 LODO | [hcmc_19_10_data.csv](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/data/processed/hcmc_19_10_data.csv) |
| **Ngày Mới (T2 tới)**| Thứ Hai | 06:00 – 12:00 | Dự kiến trọn vẹn 06:00 – 12:00 (Tắt Sleep Windows) | Fold 5 LODO (Test độc lập) | Kịch bản [scheduled_crawler.py](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/01_ingestion/scheduled_crawler.py) |
| *20/10/2026* | *Thứ Ba* | *10:31 – 23:55* | *Bắt đầu lúc 10:31 (Khuyết toàn bộ cao điểm sáng)* | *Loại khỏi tập hiệu chuẩn sáng* | *[data_hcmc_20_10.csv](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/data/processed/data_hcmc_20_10.csv)* |
| *30/10/2026* | *Thứ Sáu*| *16:00 – 19:00* | *Khung cao điểm chiều (Khác tính chất cao điểm sáng)* | *Chỉ dùng khảo sát độ nhạy cũ*| *[run_lambda_sensitivity_study.py](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/run_lambda_sensitivity_study.py)* |

---

### 3. Danh mục Nhiệm vụ Chi tiết (Action Tasks)

#### Nhiệm vụ 1.1: Chuẩn hóa Tập dữ liệu Đầu vào & Mặt nạ Trọng số Độ tin cậy (Soft Masking)
* **Dùng cái gì:**
  * Bảng dữ liệu: [macro_traffic_history.csv](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/data/processed/macro_traffic_history.csv) và [hcmc_19_10_data.csv](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/data/processed/hcmc_19_10_data.csv).
  * Mã nguồn: `macro_traffic_crawler/02_calibration/prepare_calibration_targets.py`.
* **Làm gì:**
  * Đồng bộ hóa dữ liệu quan sát trên 66 cạnh đo định danh cho 7 khung giờ 30 phút: `["06:30", "07:00", "07:30", "08:00", "08:30", "09:00", "09:30"]`.
  * Thay thế quy tắc lọc cứng $c \ge 0.70$ (loại gây mất dữ liệu/NaN) bằng cơ chế **Soft Masking**:
    * Với mỗi cạnh $e$ và lát cắt thời gian $t$, nếu độ tin cậy $c_{e, t} < 0.30$, gán mặt nạ $m_{e, t} = 0$.
    * Với $c_{e, t} \ge 0.30$, gán $m_{e, t} = 1$ và tính trọng số nghịch đảo phương sai:
      $$w_{e, t} = \frac{m_{e, t} \cdot c_{e, t}}{\sum_{e'=1}^{66} m_{e', t} \cdot c_{e', t}}$$
  * Nhóm 66 cạnh đo thành **8 – 12 hành lang trục chính (Corridors)**: Điện Biên Phủ, Nguyễn Thị Minh Khai, Cách Mạng Tháng 8, Nam Kỳ Khởi Nghĩa, Pasteur, Hai Bà Trưng, Đinh Tiên Hoàng, Lê Duẩn, Võ Văn Tần, Nguyễn Đình Chiểu.
  * Tính toán Free-flow Baseline ($v_0$) và Historical Median của vận tốc quan sát cho từng lát cắt.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Tạo ma trận mục tiêu $\mathbf{V}_{\text{obs}} \in \mathbb{R}^{66 \times 7}$ và ma trận trọng số $\mathbf{W} \in \mathbb{R}^{66 \times 7}$ không chứa phần tử `NaN`.
  * [ ] Bảng định nghĩa nhóm hành lang: `macro_traffic_crawler/data/metadata/corridor_definitions.json` (tối thiểu 8 hành lang, mỗi hành lang gồm 3–8 cạnh đo kết nối liên tục).

#### Nhiệm vụ 1.2: Xây dựng Pipeline Tối ưu hóa CMA-ES Đa tiến trình (Parallel CMA-ES)
* **Dùng cái gì:**
  * Thư viện tối ưu: `cma` (Hansen's Covariance Matrix Adaptation Evolution Strategy) hoặc `optuna.samplers.CmaEsSampler`.
  * Mô hình mạng lưới: [data/raw_data/q1_map.net.xml](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/data/raw_data/q1_map.net.xml) (đúng 34 nút giao có đèn, Sublane 0.25m, đèn vàng 3.0s).
  * Bộ sinh luồng: `randomTrips.py` + `duarouter` (`--fringe-factor 8.0`, `--min-distance 400.0`).
  * Thực thi song song: `multiprocessing.Pool` (song song hóa việc đánh giá các cá thể trên các lõi CPU).
* **Làm gì:**
  * Xây dựng mô đun: `macro_traffic_crawler/02_calibration/calibrate_cmaes.py`.
  * Thiết lập không gian tối ưu hóa 7 chiều: $\boldsymbol{\lambda} = [\lambda_1, \dots, \lambda_7]^T \in [0.10, 3.00]^7$.
  * Cấu hình tham số CMA-ES:
    * Kích thước quần thể: $\lambda_{\text{pop}} = 4 + \lfloor 3 \ln(7) \rfloor \approx 9$ cá thể / thế hệ.
    * Số thế hệ tối đa: $G_{\text{max}} = 10 – 12$ thế hệ (Tổng cộng $\approx 90 – 108$ lượt chạy mô phỏng).
    * Giảm thiểu nhiễu ngẫu nhiên: Áp dụng kỹ thuật Common Random Numbers (CRN - dùng chung 2 random seeds, ví dụ: seed 42 và seed 100, lấy trung bình kết quả đánh giá).
  * Hàm mục tiêu có trọng số độ tin cậy và điều chuẩn:
    $$\min_{\boldsymbol{\lambda}} \mathcal{L}(\boldsymbol{\lambda}) = \sum_{t=1}^7 \sum_{e=1}^{66} w_{e, t} \left( v_{\text{sim}, e}(\boldsymbol{\lambda}, t) - v_{\text{obs}, e}(t) \right)^2 + \gamma_{\text{smooth}} \|\Delta^2 \boldsymbol{\lambda}\|^2 + \gamma_{\text{prior}} \|\boldsymbol{\lambda} - \boldsymbol{\lambda}_{\text{prior}}\|^2 + w_{\text{pen}} \cdot \mathcal{P}_{\text{BPR}}^{\text{norm}}(\boldsymbol{\lambda})$$
  * Thiết lập giai đoạn khởi động Warm-up 06:00 – 06:30 nạp lưu lượng trước khi bắt đầu đo đạc tại 06:30.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Đo đạc tốc độ thực thi: Mỗi thế hệ 9 cá thể chạy song song hoàn thành trong $\le 45$ phút trên máy trạm đa nhân.
  * [ ] Quá trình tối ưu hóa hội tụ sau 10–12 thế hệ, không bị crash hoặc treo tiến trình SUMO con.
  * [ ] Tỷ lệ xe bị dịch chuyển tức thời (teleport rate) duy trì $< 0.1\%$, tỷ lệ nạp $ICR \ge 95\%$, tỷ lệ tồn đọng cửa ngõ $GBR < 5\%$.

#### Nhiệm vụ 1.3: Thu thập Bổ sung Dữ liệu Ngày Thứ 5 Hợp lệ
* **Dùng cái gì:**
  * Kịch bản thu thập: [macro_traffic_crawler/01_ingestion/scheduled_crawler.py](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/01_ingestion/scheduled_crawler.py).
  * Cấu hình nguồn điện hệ thống: Thiết lập Windows Power Plan sang chế độ *Never Sleep* / *High Performance*.
* **Làm gì:**
  * Thu thập dữ liệu giao thông TomTom liên tục trong khung giờ 06:00 – 12:00 vào sáng Thứ Hai kế tiếp.
  * Chuẩn hóa dữ liệu cào được vào `macro_traffic_crawler/data/processed/hcmc_day5_data.csv`.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Đủ 5 ngày làm việc độc lập có trọn vẹn khung cao điểm sáng: 14/10 (T4), 15/10 (T5), 16/10 (T6), 19/10 (T2), và Ngày mới (T2).

#### Nhiệm vụ 1.4: Thực thi Kiểm định Chéo Leave-One-Day-Out (LODO) & Nghiệm thu Khoa học
* **Dùng cái gì:**
  * Bộ công cụ kiểm định: [evaluation/level1_macro_flow/statistical_tester.py](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/evaluation/level1_macro_flow/statistical_tester.py).
  * Bộ đo lường vận tốc: [evaluation/level1_macro_flow/speed_metrics.py](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/evaluation/level1_macro_flow/speed_metrics.py).
* **Làm gì:**
  * Thực hiện quy trình xoay vòng 5-fold LODO: Huấn luyện $\boldsymbol{\lambda}^*$ trên 4 ngày, kiểm tra trên ngày độc lập còn lại.
  * Đánh giá bộ chỉ số nghiệm thu khoa học thực tế:
    1. **Sai số độ lệch vận tốc toàn mạng (Whole-network Speed Bias):**
       $$|\text{Bias}_v(t)| = \left| \frac{1}{|\mathcal{E}_t|} \sum_{e \in \mathcal{E}_t} v_{\text{sim}, e}(t) - \frac{1}{|\mathcal{E}_t|} \sum_{e \in \mathcal{E}_t} v_{\text{obs}, e}(t) \right| \le 2.0\text{ km/h} \quad (\forall t \in \{1, \dots, 7\})$$
    2. **Tương quan hạng cấp hành lang (Corridor-level Spearman Rank):**
       $$\rho_{\text{corridor}} = \text{SpearmanRank}\left( \bar{v}_{\text{sim}}^{\text{corridor}}, \bar{v}_{\text{obs}}^{\text{corridor}} \right) \ge 0.50$$
       (Nhận diện đúng thứ tự các trục đường ùn tắc nặng nhất: ĐBP, NTMK, CMT8 so với các trục thông thoáng hơn).
    3. **Chỉ số Kỹ năng Tương đối (Skill Score):**
       $$\text{Skill Score} = 1 - \frac{\text{RMSE}(\boldsymbol{\lambda}^*)}{\text{RMSE}_{\text{ref}}} > 0$$
       với mốc đối chuẩn là Free-flow Baseline ($v_0$) và Constant Demand Baseline ($\boldsymbol{\lambda} \equiv 1.0$).
    4. **Khoảng cách Phân bố Wasserstein:** $W_1(P_{\text{sim}}, P_{\text{obs}})$ giảm $\ge 25\%$ so với nghiệm khởi tạo $\boldsymbol{\lambda}^{(0)}$.
    5. **Kiểm tra Thoát nghẽn (Drain Check):** Sau khi kết thúc nạp xe lúc 09:30, kích hoạt 30 phút xả mạng (09:30–10:00), đảm bảo tỷ lệ hoàn thành $TCR_{\text{drain}} \ge 90\%$, không có hiện tượng nghẽn tích lũy vĩnh viễn (unrecoverable gridlock).
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Đạt toàn bộ 5 tiêu chuẩn nghiệm thu khoa học nêu trên trên cả 5 folds LODO.
  * [ ] Xuất tệp báo cáo thống kê chính thức: `evaluation/benchmark_reports/level1_lodo_results.json` và biểu đồ kiểm định `evaluation/figures/lodo_validation_report.png`.

#### Nhiệm vụ 1.5: Khóa Kịch bản & Lưu Snapshot Trạng thái Khởi động (Warm-up State)
* **Dùng cái gì:**
  * Tệp cấu hình: `sumo_scenarios/q1_calibrated_morning/`.
* **Làm gì:**
  * Xuất tệp lộ trình tối ưu trung bình: `calibrated_morning_peak.rou.xml` chứa cấu hình nạp xe theo $\boldsymbol{\lambda}^*$.
  * Chạy mô phỏng giai đoạn khởi động 06:00 – 07:00 một lần duy nhất với tùy chọn `--save-state sumo_scenarios/q1_calibrated_morning/checkpoint_warmup_0700.xml`.
  * Khóa cứng toàn bộ tài nguyên (Freeze Scenario) để bàn giao sang Chặng 2.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Tệp `checkpoint_warmup_0700.xml` được tạo hợp lệ, nạp lại thành công bằng tùy chọn `--load-state` trong SUMO mà không phát sinh lỗi trạng thái.

#### Nhiệm vụ 1.6: Soạn thảo Bản thảo Chương 2 & Chương 3 Khóa luận Tốt nghiệp
* **Dùng cái gì:**
  * Báo cáo lý thuyết: [BPR_SENSITIVITY_AND_CALIBRATION_FOUNDATION.md](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/docs/BPR_SENSITIVITY_AND_CALIBRATION_FOUNDATION.md).
  * Quy chuẩn mô phỏng: [HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/docs/HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md).
  * Kết quả LODO từ Nhiệm vụ 1.4.
* **Làm gì:**
  * Viết dứt điểm vào bản thảo luận văn:
    * **Chương 2 (Tổng quan Lý thuyết & Phản biện Hàm BPR):** Trình bày chứng minh toán học điểm kỳ dị $\lim_{v \to v_0}\mathcal{E}_v = -\infty$, sự vi phạm định luật bảo toàn Kirchhoff khi tối ưu cục bộ, và lý do toán học chuyển sang hiệu chuẩn toàn cục với biên mềm $\mathcal{P}_{\text{BPR}}^{\text{norm}}$.
    * **Chương 3 (Mô hình Mô phỏng Vi mô & Quy trình Hiệu chuẩn Nhu cầu CMA-ES):** Trình bày mô hình Sublane $85/12/3$, thuật toán CMA-ES song song, kỹ thuật Warm-up 06:00, và bảng kết quả nghiệm thu 5-fold LODO.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Hoàn thành trọn vẹn văn bản Chương 2 và Chương 3 (khoảng 25 – 35 trang tài liệu học thuật), sẵn sàng ghép nối vào báo cáo giữa kỳ / seminar.

---

## CHẶNG 2: XÂY DỰNG ADAPTER SUMO-RL, BASELINES CỔ ĐIỂN & SUB-NETWORK SMOKE TEST (NGÀY 13 – NGÀY 22)

### 1. Mục tiêu Chặng 2
* Khảo sát toàn diện khung toán học Dec-POMDP (State, Action, Reward) cho điều khiển tín hiệu giao thông đô thị; đối chiếu ưu nhược điểm với dòng xe máy hỗn hợp Sublane nhưng **chưa chốt cứng Agent** để thảo luận thêm.
* Xây dựng lớp giao tiếp môi trường kỹ thuật chuẩn hóa (Environment Adapter) kết nối mạng lưới SUMO 34 nút giao với Python qua `libsumo` / `traci`.
* Tích hợp cơ chế tải trước trạng thái `--load-state checkpoint_warmup_0700.xml` giúp tiết kiệm 25–30% thời gian chạy bằng cách bỏ qua giai đoạn warm-up ở từng episode.
* Triển khai các mốc đối chuẩn truyền thống (Rule-based Baselines) gồm: **Fixed-Time chuẩn** (chu kỳ 90s), **Webster Allocation** (phân bổ thời gian xanh theo tải), và **Max-Pressure cải tiến** (Varaiya, 2013) được định nghĩa lại ở cấp chuyển động (movement-level) cho dòng xe không phân làn.
* Tiến hành chạy thử nghiệm kiểm tra tích hợp (Smoke Test) thuật toán IDQN từ thư viện mã nguồn mở (**LibSignal** hoặc **RESCO**) trên mạng con (Sub-network 3–6 nút giao) để đảm bảo tính sẵn sàng trước khi sang Chặng 3.
* **Viết song song:** Soạn thảo phần phương pháp luận của Chương 4 (Môi trường Adapter & Mô hình Baseline).

---

### 2. Danh mục Nhiệm vụ Chi tiết (Action Tasks)

#### Nhiệm vụ 2.1: Khảo sát, Tổng hợp & So sánh Khung Toán học Dec-POMDP từ các Công trình Tiêu biểu
* **Dùng cái gì:**
  * Các bài báo kinh điển: CoLight (Zheng et al., CIKM 2019 [8]), PressLight (Wei et al., KDD 2019 [10]), MPLight (Chen et al., AAAI 2020 [9]), FRAP (Zheng et al., KDD 2019), RESCO Benchmark (Ault & Benton, NeurIPS 2021).
* **Làm gì:**
  * Khảo sát các phương án thiết kế không gian quan sát cục bộ $\mathcal{O}_i$: Hàng đợi (Queue), thời gian chờ (Delay), số lượng xe (Vehicle counts), áp lực chênh lệch (Pressure).
  * Khảo sát các phương án thiết kế không gian hành động $\mathcal{A}_i$: Chọn pha trực tiếp (Phase Selection), Chuyển pha an toàn (Phase Switch), hoặc Điều chỉnh thời lượng xanh (Green Duration).
  * Khảo sát các phương án thiết kế hàm thưởng $\mathcal{R}_i$: Phạt hàng đợi tức thời, phạt áp lực phân tán, phạt độ trễ tích lũy.
  * Phân tích tính tương thích của từng phương án đối với dòng xe máy hỗn hợp Sublane (nơi không thể đếm xe theo từng làn cố định mà phải tổng hợp theo nhánh tiếp cận hoặc diện tích mặt cắt).
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Xuất bản tệp khảo sát học thuật: `macro_traffic_crawler/docs/MARL_FORMULATION_SURVEY.md` chứa bảng đối chiếu các công trình quốc tế.
  * [ ] Đưa ra các gợi ý định hướng thiết kế nhưng **chưa khóa cứng**, làm tài liệu thảo luận trước khi bước vào lập trình Agent.

#### Nhiệm vụ 2.2: Xây dựng Lớp Wrapper Kỹ thuật Giao tiếp SUMO qua Python (Environment Adapter)
* **Dùng cái gì:**
  * Thư viện: `libsumo`, `traci`.
  * Tài nguyên kịch bản: `sumo_scenarios/q1_calibrated_morning/` đã khóa ở Chặng 1 kèm tệp `checkpoint_warmup_0700.xml`.
* **Làm gì:**
  * Tạo tệp module: `marl_environment/sumo_adapter.py`.
  * Hỗ trợ cơ chế nạp Hybrid: ưu tiên `import libsumo as traci` khi huấn luyện ngầm tốc độ cao, chuyển đổi sang `import traci` khi cần bật giao diện GUI để quan sát hành vi.
  * Xây dựng các phương thức cốt lõi:
    * `reset(seed=None)`: Nạp trạng thái mạng từ `checkpoint_warmup_0700.xml` thông qua tùy chọn `--load-state`, đưa môi trường bắt đầu ngay từ thời điểm $t = 07:00$ mà không tốn chi phí chạy lại 1.800s warm-up.
    * `step(actions)`: Áp dụng hành động chọn pha tại 34 nút giao, tự động chèn $t_{\text{yellow}} = 3.0\text{s}$ an toàn khi có sự thay đổi pha xanh, thực hiện mô phỏng qua thời lượng hành động $\Delta t_{\text{action}} = 5.0\text{s}$ (tương ứng 25 bước tích phân vi mô).
    * `get_observations()`: Trích xuất số lượng xe và hàng đợi trên từng nhánh tiếp cận của 34 nút giao (được làm mịn diện tích cho mô hình Sublane).
    * `get_rewards(reward_type)`: Cung cấp các cấu hình hàm thưởng linh hoạt (Queue, Delay, Pressure).
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Viết test tự động `marl_environment/test_sumo_adapter.py`, chạy 200 bước hành động liên tục không phát sinh lỗi rò rỉ bộ nhớ hoặc lỗi đồng bộ TraCI.
  * [ ] Tốc độ thực thi đạt $\ge 45$ steps/s khi chạy ngầm với `libsumo`.

#### Nhiệm vụ 2.3: Triển khai & Đo đạc Baselines Cổ điển (Fixed-Time, Webster, Offset Coordination)
* **Dùng cái gì:**
  * Module kết nối: `marl_environment/sumo_adapter.py`.
  * Cấu hình điều khiển:
    1. **Fixed-Time Baseline:** Chu kỳ 90s cố định (pha xanh chia đều theo hình học).
    2. **Webster Allocation Baseline:** Phân bổ thời lượng pha xanh tỷ lệ thuận với lưu lượng bão hòa và nhu cầu giờ cao điểm theo công thức Webster cổ điển:
       $$g_j = \frac{y_j}{Y} (C - L)$$
* **Làm gì:**
  * Viết mã nguồn điều khiển: `baselines/traditional/fixed_time.py` và `baselines/traditional/webster.py`.
  * Chạy mô phỏng trên toàn bộ khung giờ hoạt động 07:00 – 09:00 (7.200s) + 30 phút xả mạng (09:00 – 09:30) trên **5 hạt giống ngẫu nhiên (Seeds: 42, 100, 2026, 777, 999)**.
  * Đo đạc 5 chỉ số hiệu năng chuẩn:
    1. Thời gian hành trình trung bình (Average Travel Time - ATT) [giây].
    2. Tổng độ trễ toàn mạng (Total Network Delay) [giờ-xe].
    3. Chiều dài hàng đợi trung bình (Average Queue Length - AQL) [xe].
    4. Tỷ lệ hoàn thành chuyến đi (Completion Rate - CR) [\%].
    5. Số lượng phương tiện bị dịch chuyển tức thời (Teleport Count).
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Báo cáo kết quả đo đạc định dạng khoa học $\text{Mean} \pm \text{Std}$ trên 5 seeds.
  * [ ] Lưu số liệu vào `evaluation/benchmark_reports/traditional_baselines.json`.

#### Nhiệm vụ 2.4: Triển khai & Kiểm chứng Giả thuyết Max-Pressure Cải tiến (Movement-level)
* **Dùng cái gì:**
  * Thuật toán: Max-Pressure Controller [Varaiya, 2013].
  * Module kết nối: `marl_environment/sumo_adapter.py`.
* **Làm gì:**
  * Viết mã nguồn: `baselines/traditional/max_pressure.py`.
  * Do dòng xe Sublane TP.HCM không tuân thủ làn cứng, định nghĩa áp lực pha $k$ tại nút giao $i$ ở cấp chuyển động (Movement-level / Inflow-Outflow approach):
    $$P_i(k) = \sum_{m \in \mathcal{M}_i(k)} \left( \frac{x_{\text{in}}(m)}{C_{\text{in}}(m)} - \frac{x_{\text{out}}(m)}{C_{\text{out}}(m)} \right)$$
    với $x(m)$ là số phương tiện trên nhánh chuyển động và $C(m)$ là sức chứa hình học tối đa.
  * Ràng buộc an toàn: Thời gian xanh tối thiểu $g_{\text{min}} = 10\text{s}$, thời gian vàng $t_{\text{yellow}} = 3\text{s}$.
  * Chạy đánh giá trên cùng **5 random seeds (Seeds: 42, 100, 2026, 777, 999)** trên khung 07:00 – 09:30 (kèm pha xả).
  * **Thiết lập Giả thuyết Mở $H_{\text{baseline}}$:** *"Cơ chế phản hồi áp lực Max-Pressure có khả năng giảm độ trễ và hàng đợi vượt trội so với Fixed-Time và Webster trong điều kiện dòng hỗn hợp không phân làn hay không?"* (Không ấn định kết quả trước khi chạy).
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Thuật toán Max-Pressure chạy ổn định trên 34 nút giao không bị chết đói pha (phase starvation).
  * [ ] Thực hiện kiểm định Paired $t$-test hoặc Wilcoxon signed-rank test giữa Max-Pressure và Fixed-Time/Webster ($n = 5$ seeds).
  * [ ] Lưu số liệu vào `evaluation/benchmark_reports/max_pressure_baseline.json`.

#### Nhiệm vụ 2.5: Khảo sát Thư viện MARL & Chạy Thử nghiệm Smoke Test trên Sub-network
* **Dùng cái gì:**
  * Bộ thư viện MARL: **LibSignal** (GitHub: `DaRL-LibSignal/LibSignal`) hoặc **RESCO**.
  * Bản đồ mạng con: Trích xuất một hành lang gồm 3–6 nút giao từ `q1_map.net.xml` (ví dụ: trục Pasteur hoặc Nam Kỳ Khởi Nghĩa).
* **Làm gì:**
  * Tạo tài liệu kế hoạch tích hợp: `marl_environment/INTEGRATION_PLAN.md` làm rõ cơ chế chuyển đổi tensor giữa SUMO và thư viện MARL.
  * Thiết lập cơ chế Padding và Masking cho các nút giao không đồng nhất (số pha biến thiên từ 2 đến 6 pha, số nhánh vào/ra khác nhau).
  * Chạy thử nghiệm kỹ thuật (Smoke Test) thuật toán IDQN trên mạng con 3–6 nút giao trong 10–20 episodes.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Tiến trình huấn luyện IDQN trên mạng con chạy thông suốt 20 episodes mà không bị lỗi kích thước tensor, rò rỉ bộ nhớ PyTorch, hoặc sụp đổ kết nối TraCI/libsumo.
  * [ ] Hoàn thành toàn bộ khâu chuẩn bị tích hợp trước khi bước vào huấn luyện mạng đầy đủ ở Chặng 3.

---

## CHẶNG 3: HUẤN LUYỆN MARL 5 SEEDS, KIỂM THỬ ĐỘ BỀN & SO SÁNH ĐỐI CHUẨN (NGÀY 23 – NGÀY 38)

### 1. Mục tiêu Chặng 3
* Chốt thiết kế toán học Dec-POMDP (State, Action, Reward) dựa trên kết quả khảo sát từ Chặng 2.
* Huấn luyện 2 mô hình học tăng cường đa tác tử:
  1. **IDQN (Independent DQN):** Baseline MARL cơ bản phân tán không giao tiếp.
  2. **CoLight (Zheng et al., CIKM 2019):** Mô hình MARL phối hợp sử dụng mạng Graph Attention (GAT) trên đồ thị 34 nút giao.
* Tối ưu hóa ngân sách tính toán thông qua chiến lược 2 giai đoạn: Tinh chỉnh siêu tham số trên cửa sổ 1 giờ / mạng con $\to$ Huấn luyện chính thức trên toàn mạng với Snapshot Warm-up và cơ chế dừng sớm (Early Stopping).
* Huấn luyện trên **5 hạt giống ngẫu nhiên (Seeds: 42, 100, 2026, 777, 999)** và đánh giá trên 10 rollout độc lập mỗi seed; báo cáo kết quả bằng **Interquartile Mean (IQM) kèm 95% Bootstrap Confidence Intervals** theo chuẩn học thuật Deep RL quốc tế (Agarwal et al., NeurIPS 2021).
* Triệt tiêu hoàn toàn Survivor Bias bằng cơ chế theo dõi Total Delay của xe chưa về đích và đo đạc tỷ lệ hoàn thành chuyến đi (Completion Rate).
* Thực hiện Stress-test kiểm tra tính bền vững ($\pm 15\%$ và $\pm 30\%$ tải) để kiểm chứng khách quan các Giả thuyết Khoa học $H_1$ và $H_2$.

---

### 2. Bảng Phân bổ Ngân sách Tính toán Chặng 3 (Computational Budget Plan)

| Nội dung Thực thi | Kích thước Mạng | Cửa sổ Episode | Thời gian 1 Episode | Số Episode | Số Lượt Chạy (Runs) | Tổng Thời gian Ước tính |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Giai đoạn 3A: Tuning Siêu tham số & Reward** | Mạng con 6 nút / Cửa sổ 1h | 07:30 – 08:30 (3.600s) | $\approx 3 – 5$ phút | 50 episodes | 4 cấu hình $\times$ 1 seed | $\approx 10 – 16$ giờ máy |
| **Giai đoạn 3B: Huấn luyện IDQN Toàn mạng** | Mạng đầy đủ 34 nút | 07:00 – 09:00 (Load State) | $\approx 10 – 12$ phút | 100–120 eps (Early Stop) | 5 seeds độc lập | $\approx 100 – 120$ giờ (chạy qua đêm) |
| **Giai đoạn 3C: Huấn luyện CoLight Toàn mạng** | Mạng đầy đủ 34 nút (GAT) | 07:00 – 09:00 (Load State) | $\approx 12 – 15$ phút | 100–120 eps (Early Stop) | 5 seeds độc lập | $\approx 120 – 150$ giờ (chạy qua đêm) |
| **Giai đoạn 3D: Đánh giá Rollout & Stress-test** | Mạng đầy đủ 34 nút | 07:00 – 09:30 (Kèm Drain) | $\approx 14 – 16$ phút | 10 rollouts / model | 4 mô hình $\times$ 3 mức tải | $\approx 28 – 32$ giờ |

---

### 3. Danh mục Nhiệm vụ Chi tiết (Action Tasks)

#### Nhiệm vụ 3.1: Chốt Khung Toán học Dec-POMDP & Cấu hình Ma trận Đồ thị Giao thông
* **Dùng cái gì:**
  * Báo cáo khảo sát: `macro_traffic_crawler/docs/MARL_FORMULATION_SURVEY.md`.
  * Mô hình mạng lưới: [data/raw_data/q1_map.net.xml](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/data/raw_data/q1_map.net.xml) (34 nút giao).
* **Làm gì:**
  * Khóa cấu hình 7 thành phần Dec-POMDP:
    * **Tác tử:** $\mathcal{N} = \{1, 2, \dots, 34\}$.
    * **Quan sát cục bộ $o_i \in \mathcal{O}_i$:** Vector gồm mật độ xe trên từng nhánh chuyển động, chỉ số hàng đợi chuẩn hóa theo diện tích Sublane, và trạng thái pha đèn hiện tại.
    * **Không gian hành động $a_i \in \mathcal{A}_i$:** Chọn pha xanh kế tiếp $k \in \{1, \dots, P_i\}$ kèm chèn pha vàng an toàn $t_{\text{yellow}} = 3.0\text{s}$ và thời gian xanh tối thiểu $g_{\text{min}} = 10\text{s}$.
    * **Hàm thưởng $r_i$:** Hàm phạt áp lực chuyển động hoặc độ trễ cục bộ:
      $$r_i = - \sum_{m \in \mathcal{M}_i} \text{Queue}_m - \beta_{\text{switch}} \cdot \mathbb{I}(\text{chuyển pha})$$
  * Xây dựng ma trận kề đồ thị nút giao $A_{\text{adj}} \in \{0, 1\}^{34 \times 34}$ dựa trên khoảng cách địa lý ($d(i, j) \le 350\text{m}$) và quan hệ kết nối luồng giao thông thực tế.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Xuất bản tệp cấu hình ma trận kề `marl_environment/adj_matrix_34nodes.npy`.
  * [ ] Kiểm tra tính toàn vẹn của tensor đồ thị khi đưa vào mô hình Graph Attention của CoLight.

#### Nhiệm vụ 3.2: Giai đoạn 3A - Tinh chỉnh Siêu tham số & Hàm thưởng (Ablation & Tuning)
* **Dùng cái gì:**
  * Mạng con 6 nút giao hoặc cửa sổ 1 giờ cao điểm (07:30 – 08:30).
  * Thuật toán: IDQN và CoLight từ LibSignal.
* **Làm gì:**
  * Thực hiện khảo sát nhanh trên 4 cấu hình hàm thưởng: (1) Phạt hàng đợi đơn thuần, (2) Phạt độ trễ, (3) Phạt áp lực Max-Pressure, (4) Hàm kết hợp kèm phạt chuyển pha.
  * Tinh chỉnh tốc độ học $\alpha \in \{10^{-4}, 5 \cdot 10^{-4}, 10^{-3}\}$ và hệ số chiết khấu $\gamma \in \{0.90, 0.95\}$.
  * Lựa chọn cấu hình cho đường cong học tập ổn định nhất để chuyển sang huấn luyện toàn mạng.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Xác định được bộ siêu tham số tối ưu duy nhất để áp dụng đồng nhất cho Giai đoạn 3B và 3C.

#### Nhiệm vụ 3.3: Giai đoạn 3B - Huấn luyện Toàn diện Independent DQN (IDQN) trên 5 Seeds
* **Dùng cái gì:**
  * Mạng đầy đủ 34 nút giao, nạp trạng thái từ `checkpoint_warmup_0700.xml`.
  * Thuật toán: IDQN từ LibSignal.
  * Hạt giống huấn luyện: 5 seeds ngẫu nhiên độc lập (Seeds: 42, 100, 2026, 777, 999).
* **Làm gì:**
  * Huấn luyện IDQN trên từng seed trong 100–120 episodes (mỗi episode mô phỏng 7.200s từ 07:00 – 09:00).
  * Kích hoạt cơ chế Early Stopping: Nếu phần thưởng trung bình trên 10 episodes kiểm định liên tiếp không cải thiện, tiến trình huấn luyện dừng sớm để tiết kiệm thời gian tính toán.
  * Lưu trữ đường cong học tập chi tiết (Reward, Loss, Epsilon) của từng seed.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Lưu trữ đủ 5 checkpoint tốt nhất: `checkpoints/idqn_seed{seed}_best.pth`.
  * [ ] Xuất tệp nhật ký huấn luyện: `logs/idqn_training_curves.csv`.

#### Nhiệm vụ 3.4: Giai đoạn 3C - Huấn luyện Toàn diện Mô hình MARL Phối hợp CoLight trên 5 Seeds
* **Dùng cái gì:**
  * Mạng đầy đủ 34 nút giao kèm ma trận kề $A_{\text{adj}}$.
  * Kiến trúc mô hình: Graph Attention Network (GAT) 2 heads, embedding 64.
  * Cùng 5 hạt giống huấn luyện: Seeds 42, 100, 2026, 777, 999.
* **Làm gì:**
  * Huấn luyện CoLight trên cùng điều kiện kịch bản và cùng giao thức dừng sớm như IDQN.
  * Cơ chế GAT cho phép các nút giao trao đổi thông tin cục bộ để học chính sách phối hợp giải tỏa áp lực theo hành lang.
  * Lưu trữ đường cong học tập của CoLight trên cả 5 seeds.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Lưu trữ đủ 5 checkpoint tốt nhất: `checkpoints/colight_seed{seed}_best.pth`.
  * [ ] Xuất tệp nhật ký huấn luyện: `logs/colight_training_curves.csv`.

#### Nhiệm vụ 3.5: Giai đoạn 3D - Đánh giá Rollout, Khử Survivor Bias & Stress-test Quá tải
* **Dùng cái gì:**
  * Toàn bộ các checkpoint tốt nhất của 4 phương pháp: Fixed-Time, Max-Pressure, IDQN, CoLight.
  * Các kịch bản biến động nhu cầu (Domain Randomization):
    1. **Nhu cầu Thấp:** $\boldsymbol{\lambda}_{\text{low}} = 0.70 \cdot \boldsymbol{\lambda}^*$ ($-30\%$).
    2. **Nhu cầu Chuẩn:** $\boldsymbol{\lambda}_{\text{normal}} = 1.00 \cdot \boldsymbol{\lambda}^*$ (Kịch bản cao điểm thực tế).
    3. **Nhu cầu Quá tải Cực đoan:** $\boldsymbol{\lambda}_{\text{high}} = 1.30 \cdot \boldsymbol{\lambda}^*$ ($+30\%$).
* **Làm gì:**
  * Thực thi 10 rollout đánh giá độc lập cho mỗi model $\times$ seed trên khung giờ 07:00 – 09:30 (trong đó 09:00 – 09:30 là pha xả mạng bắt buộc).
  * Thu thập đồng thời các chỉ số khử Survivor Bias:
    * **Completion Rate ($CR$):** $CR = \frac{N_{\text{arrived}}}{N_{\text{departed}}} \times 100\%$.
    * **Virtual Total Delay ($TD_{\text{total}}$):** Cộng thêm thời gian dự kiến cho các xe chưa về đích:
      $$TD_{\text{total}} = \sum_{v \in \mathcal{V}_{\text{arrived}}} \text{Delay}_v + \sum_{v' \in \mathcal{V}_{\text{uncompleted}}} \left( \text{Delay}_{v'}^{\text{current}} + \frac{d_{\text{remaining}}}{v_0} \right)$$
    * **Teleport Count:** Kiểm tra xe bị kẹt dịch chuyển tức thời (bắt buộc $< 0.1\%$).
  * **Kiểm chứng các Giả thuyết Khoa học Khách quan:**
    * **Giả thuyết $H_1$ (Tính hiệu quả của Giao tiếp Đồ thị GAT):** So sánh IQM của độ trễ và sự đồng đều hàng đợi hành lang giữa CoLight và IDQN trong điều kiện chuẩn.
    * **Giả thuyết $H_2$ (Khả năng Chống sụp đổ Mạng lưới khi Quá bão hòa):** Phân tích sự suy giảm của Completion Rate ($CR$) và hiện tượng nghẽn mạng dây chuyền khi nhu cầu tăng vọt $+30\%$.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Báo cáo số liệu dạng **Interquartile Mean (IQM) kèm 95% Bootstrap Confidence Intervals** (tính toán qua 10.000 bootstrap resamples) theo chuẩn Agarwal et al. (NeurIPS 2021).
  * [ ] Lưu toàn bộ bảng dữ liệu đối chuẩn vào: `evaluation/benchmark_reports/final_evaluation_results.csv`.

---

## CHẶNG 4: PHÂN TÍCH THỰC NGHIỆM, VIẾT KHÓA LUẬN & BÁO CÁO SEMINAR (NGÀY 39 – NGÀY 50)

### 1. Mục tiêu Chặng 4
* Xây dựng bộ biểu đồ khoa học trực quan hóa toàn diện kết quả thực nghiệm đạt chuẩn xuất bản (Publication-Quality Figures, 300 DPI).
* Hoàn thiện bản thảo toàn diện của Khóa luận Tốt nghiệp (kết hợp các Chương 2 & 3 đã viết sẵn ở Chặng 1, Phương pháp luận ở Chặng 2, và phân tích thực nghiệm Chặng 3).
* Soạn thảo bản thảo Bài báo Khoa học chuẩn IEEE Conference (6 – 8 trang).
* Chuẩn bị Slide thuyết trình Seminar / Bảo vệ và kịch bản trả lời chất vấn phản biện 45 giây.
* Dành **3 ngày đệm cuối cùng (Ngày 48 – 50)** làm dự phòng tuyệt đối cho việc chỉnh format, in ấn luận văn và đóng gói kho lưu trữ mã nguồn mở có khả năng tái lập kết quả (Reproducible Release).

---

### 2. Tiến độ Thực thi Chi tiết Theo Ngày (Day-by-Day Execution)

```
[Ngày 39 - 41] ────────► [Ngày 42 - 45] ────────► [Ngày 46 - 47] ────────► [Ngày 48 - 50]
  Vẽ Biểu đồ Chuẩn         Hoàn thiện Luận văn      Soạn Slide Seminar       3 NGÀY ĐỆM DỰ PHÒNG:
  Khoa học & Tính IQM      & Paper Draft (IEEE)     & Kịch bản Phản biện     In ấn, Đóng gói Git Release
```

---

### 3. Danh mục Nhiệm vụ Chi tiết (Action Tasks)

#### Nhiệm vụ 4.1: Xây dựng Bộ Biểu đồ Trực quan hóa Khoa học Đạt Chuẩn Xuất bản
* **Dùng cái gì:**
  * Thư viện: `matplotlib`, `seaborn`, `scipy.stats`.
  * Dữ liệu: `evaluation/benchmark_reports/final_evaluation_results.csv` và nhật ký huấn luyện.
* **Làm gì:**
  * Viết mã nguồn vẽ tự động: `evaluation/scripts/generate_paper_plots.py`.
  * Xuất bản 4 cụm biểu đồ đạt chuẩn 300 DPI:
    1. **Learning Curves:** Đường cong tiến hóa phần thưởng của CoLight vs. IDQN thể hiện IQM và dải phân vị $25\% – 75\%$ trên 5 seeds.
    2. **Overall Performance Comparison:** Biểu đồ thanh so sánh ATT, Delay, Throughput và Completion Rate ($CR$) giữa 4 phương pháp (Fixed-Time, Webster, Max-Pressure, IDQN, CoLight) kèm thanh sai số 95% Bootstrap CI.
    3. **Oversaturation Degradation Curve (Stress-test):** Đường cong biểu diễn sự biến thiên của Completion Rate và Tổng độ trễ khi lưu lượng nạp thay đổi từ $-30\% \to +30\%$.
    4. **Corridor Speed & Queue Heatmap:** Bản đồ nhiệt biểu diễn độ dài hàng đợi theo không gian trên các trục giao thông chính (ĐBP, NTMK, CMT8) để chứng minh hiệu quả phối hợp của cơ chế Graph Attention.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Toàn bộ biểu đồ được xuất dạng `.pdf` (vector) và `.png` (300 DPI) trong thư mục `evaluation/figures/`.
  * [ ] Đúng quy chuẩn đồ họa IEEE/ACM: font chữ đồng nhất, trục tọa độ rõ ràng, màu sắc thân thiện với người mù màu.

#### Nhiệm vụ 4.2: Hoàn thiện Toàn bộ Bản thảo Khóa luận Tốt nghiệp
* **Dùng cái gì:**
  * Mẫu văn bản: Luận văn Tốt nghiệp ĐHQG-HCM / ĐH Bách Khoa (Word hoặc LaTeX/Overleaf).
  * Nội dung đã viết sẵn: Chương 2 & 3 (từ Chặng 1), Phương pháp luận Adapter & Baseline (từ Chặng 2).
  * Số liệu thực nghiệm Chặng 3 và bộ hình ảnh Chặng 4.1.
* **Làm gì:**
  * Tích hợp và hoàn thiện toàn bộ 5 chương của Khóa luận:
    * **Chương 1: Mở đầu:** Bối cảnh ùn tắc giao thông TP.HCM, rào cản thiếu vòng từ và dữ liệu vi mô, đóng góp khoa học của đề tài.
    * **Chương 2: Cơ sở Lý thuyết & Phản biện Mô hình BPR:** Đã hoàn thiện từ Chặng 1.
    * **Chương 3: Mô hình Mô phỏng Vi mô Sublane & Hiệu chuẩn Nhu cầu CMA-ES:** Đã hoàn thiện từ Chặng 1.
    * **Chương 4: Điều khiển Tín hiệu Giao thông Đa tác tử (MARL):** Khung Dec-POMDP, cấu trúc Graph Attention của CoLight, thuật toán Max-Pressure cấp chuyển động.
    * **Chương 5: Kết quả Thực nghiệm & Thảo luận:** Bảng số liệu IQM, thảo luận kiểm chứng các giả thuyết $H_1, H_2$, phân tích hiện tượng sụp đổ mạng lưới khi quá tải, hạn chế của mô hình và hướng mở rộng.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Bản thảo Khóa luận hoàn chỉnh (khoảng 60 – 80 trang), tuân thủ 100% quy chuẩn liêm chính học thuật `GEMINI.md`.
  * [ ] Danh mục tài liệu tham khảo đồng bộ chuẩn IEEE/ACM bằng BibTeX, không có trích dẫn ma.

#### Nhiệm vụ 4.3: Soạn thảo Bản thảo Bài báo Khoa học (Paper Draft - 6 to 8 Pages)
* **Dùng cái gì:**
  * Mẫu bài báo: IEEE Conference Format (LaTeX template).
* **Làm gì:**
  * Cô đọng kết quả nghiên cứu thành bài báo khoa học tiếng Anh (6 – 8 trang) tập trung vào 2 đóng góp học thuật cốt lõi:
    1. *Đóng góp 1:* Xây dựng môi trường mô phỏng vi mô dòng hỗn hợp Sublane đầu tiên tại TP.HCM được hiệu chuẩn toàn cục qua probe data TomTom bằng thuật toán song song CMA-ES.
    2. *Đóng góp 2:* Nghiên cứu thực nghiệm đối chuẩn về tính bền vững và khả năng chống sụp đổ thông lượng của mô hình CoLight so với Max-Pressure trong điều kiện dòng xe máy quá bão hòa sâu.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Bản thảo hoàn thiện các phần: Abstract, Introduction, Related Work, Formulation & Environment, Experimental Setup, Results & Discussion, Conclusion.

#### Nhiệm vụ 4.4: Thiết kế Slide Thuyết trình Seminar / Bảo vệ & Kịch bản Phản biện
* **Dùng cái gì:**
  * Bộ hình ảnh Chặng 4.1.
  * Kịch bản phản biện miệng 45 giây từ [BPR_SENSITIVITY_AND_CALIBRATION_FOUNDATION.md](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/docs/BPR_SENSITIVITY_AND_CALIBRATION_FOUNDATION.md).
* **Làm gì:**
  * Xây dựng bộ trình chiếu PowerPoint/Canva (25 – 30 slides) tập trung vào tính logic và các bằng chứng thực nghiệm:
    * Bối cảnh đô thị TP.HCM $\to$ Bế tắc dữ liệu $\to$ Giải pháp hiệu chuẩn probe vi mô $\to$ Phản biện BPR cũ $\to$ Khung Dec-POMDP & CoLight $\to$ Bằng chứng IQM $\to$ Kết luận.
  * Chuẩn bị kịch bản trả lời dứt khoát cho 3 câu hỏi chất vấn trọng tâm của Hội đồng khoa học:
    1. *Câu hỏi 1:* "Tại sao không dùng BPR nghịch đảo để tính lưu lượng từng cạnh?" $\to$ Trả lời bằng điểm kỳ dị toán học $\lim_{v \to v_0}\mathcal{E}_v = -\infty$ và vi phạm cân bằng Kirchhoff.
    2. *Câu hỏi 2:* "Tại sao phải áp dụng mô hình Sublane 0.25m?" $\to$ Trả lời bằng đặc tính luồn lách tự nhiên của 85% xe máy và triệt tiêu sai số làm tròn hình học của SUMO.
    3. *Câu hỏi 3:* "Tại sao CoLight có thể giải quyết quá tải tốt hơn kiểm soát độc lập?" $\to$ Trả lời bằng cơ chế trao đổi thông điệp Graph Attention giúp các nút thượng lưu chủ động giữ xe, giải tỏa áp lực cho nút hạ lưu.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Bộ slide hoàn thành, cấu trúc trực quan, thời lượng trình bày khớp chuẩn 15 – 20 phút.

#### Nhiệm vụ 4.5: Thời gian Đệm Dự phòng, In ấn & Đóng gói Phát hành Git (Buffer & Release)
* **Dùng cái gì:**
  * Toàn bộ kho lưu trữ mã nguồn dự án.
* **Làm gì:**
  * Dành trọn vẹn 3 ngày cuối (Ngày 48 – 50) để xử lý các công việc hậu kỳ:
    * Kiểm tra lỗi chính tả, căn lề và in ấn luận văn theo quy chuẩn của trường.
    * Dọn dẹp các tệp tạm, cache `.pyc`, log rác trong kho mã nguồn.
    * Cập nhật tệp [README.md](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/README.md) hướng dẫn chạy tái lập toàn bộ thí nghiệm bằng 1 dòng lệnh (One-line Execution Reproducibility).
    * Gắn thẻ phát hành mã nguồn mở chính thức trên Git: `v1.0-final-release`.
* **Điều kiện hoàn thành (Acceptance Criteria):**
  * [ ] Toàn bộ tài liệu được bàn giao đúng hạn không phát sinh trễ lịch.
  * [ ] Một người dùng độc lập có thể clone kho mã nguồn và tái lập được kết quả mô phỏng theo đúng hướng dẫn.

---
*(Bản kế hoạch hành động 50 ngày được phê duyệt và lưu trữ chính thức tại kho mã nguồn của đề tài).*
