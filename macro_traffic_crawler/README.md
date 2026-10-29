# Macro Traffic Crawler & Simulation Bridge Module
================================================================================
Dự án: Multi-Agent Reinforcement Learning for Traffic Signal Control (MARL-TSC)
Khu vực nghiên cứu: Trung tâm Quận 1 & Quận 3, TP. Hồ Chí Minh
================================================================================

Module này đảm nhận toàn bộ quy trình từ **thu thập dữ liệu giao thông thực tế vĩ mô (TomTom API)**, **hiệu chuẩn hàm kháng trở BPR đặc thù dòng xe máy Việt Nam**, đến **chuyển đổi và kiểm chuẩn nhu cầu vi mô cho SUMO**.

---

## Kiến Trúc Cấu Trúc Thư Mục (Sequential Pipeline Architecture)

Thư mục đã được tái cấu trúc theo mô hình tuần tự 4 giai đoạn nghiên cứu:

```text
macro_traffic_crawler/
├── config.py                      # Cấu hình trung tâm (quản lý đường dẫn toàn cục, bounding box, API URL)
├── requirements.txt               # Thư viện phụ thuộc (requests, pandas, optuna, scipy, ...)
├── .env / .env.example            # Khóa xác thực TomTom API Keys & tham số crawl
├── README.md                      # Tài liệu hướng dẫn sử dụng (tệp này)
│
├── 01_ingestion/                  # [Giai đoạn 1: Thu thập & Cào dữ liệu TomTom]
│   ├── extract_osm_points.py      # Trích xuất 66 điểm đo GPS từ mạng lưới q1_map.osm (kèm số làn TCVN)
│   ├── tomtom_client.py           # Client gọi API TomTom Traffic Flow (hỗ trợ rate-limit & mock mode)
│   ├── key_rotator.py             # Cơ chế tự động xoay vòng nhiều API keys chống cạn quota
│   ├── run_crawler.py             # Script chạy cào dữ liệu đơn lẻ (tính sẵn BPR flow)
│   ├── scheduled_crawler.py       # Hệ thống cào tự động theo các khung giờ cao điểm/thấp điểm
│   └── PIPELINE_DOCUMENTATION.txt # Tài liệu kỹ thuật chi tiết của pipeline cào dữ liệu
│
├── 02_calibration/                # [Giai đoạn 2: Hiệu chuẩn Hàm BPR & Tối ưu hóa Tham số]
│   ├── calibrate_bpr_optuna.py    # Tối ưu hóa Bayes (Optuna TPESampler) tìm alpha, beta tối ưu
│   ├── calibrate_bpr_optuna.ipynb # Jupyter notebook trực quan hóa quá trình hội tụ và đối chuẩn
│   └── recalculate_bpr_history.py # Tiện ích cập nhật lại lưu lượng BPR trên các CSV đã cào
│
├── 03_dynamics_analysis/          # [Giai đoạn 3: Phân tích Động lực học Mạng lưới (Tùy chọn)]
│   ├── traffic_dynamics_analyzer.py # Phân tích TLCC, Hierarchical Clustering, Heatmaps Không - Thời gian
│   └── TRAFFIC_DYNAMICS_REPORT.md   # Báo cáo kết quả phân tích động lực học chuỗi thời gian
│   *(Lưu ý: Module này độc lập hoàn toàn, có thể bỏ qua hoặc xóa đi nếu không cần đưa vào luận văn).*
│
├── 04_sumo_bridge/                # [Giai đoạn 4: Cầu nối SUMO & Thẩm định Kiểm chuẩn GEH]
│   ├── generate_sumo_counts.py    # Quy đổi PCU (TCVN 104:2007) & sinh file đếm edge_counts.xml
│   └── evaluate_simulation_geh.py # Kiểm chuẩn đối sánh GEH (UK DMRB) và Vận tốc thực nghiệm
│
├── data/                          # [Thư mục dữ liệu phân tầng]
│   ├── metadata/                  # sampling_points.csv, crawler_state.json
│   ├── raw/                       # JSON snapshots thô cào từ TomTom theo timestamp
│   ├── processed/                 # CSV tổng hợp (data_hcmc_20_10.csv, bpr_best_params.json, ...)
│   └── analysis_reports/          # JSON reports & figures/ của phân tích động lực học
│
└── docs/                          # [Tài liệu học thuật & Cơ sở lý thuyết]
    ├── HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md      # Đặc tả tham số vi mô xe máy & mô hình Sublane
    ├── BPR_CALIBRATION_AND_BASELINE_EXPERIMENTS.md     # Đối chuẩn thực nghiệm Singh (1999) vs Optuna
    ├── MATHEMATICS STRUCTURES MODELING TSC.md          # Khung toán học Dec-POMDP và quy chuẩn MARL
    ├── SD_EVALUATION.md                               # Đánh giá cấu trúc dữ liệu mô phỏng
    └── SIMULATION_DATA_GENERATION.md                  # Hướng dẫn tạo lập dữ liệu mô phỏng
```

---

## Hướng Dẫn Vận Hành Từng Giai Đoạn

### Giai đoạn 1: Thu thập Dữ liệu TomTom
```bash
# 1. Trích xuất danh sách điểm đo GPS từ bản đồ OSM
python macro_traffic_crawler/01_ingestion/extract_osm_points.py

# 2. Chạy cào snapshot đơn lẻ
python macro_traffic_crawler/01_ingestion/run_crawler.py

# 3. Hoặc chạy daemon tự động lên lịch quét định kỳ
python macro_traffic_crawler/01_ingestion/scheduled_crawler.py
```

### Giai đoạn 2: Hiệu chuẩn Hàm BPR
```bash
# Chạy tối ưu hóa tham số BPR bằng Bayesian Optimization (Optuna)
python macro_traffic_crawler/02_calibration/calibrate_bpr_optuna.py --trials 20 --duration 600

# Hoặc mở Jupyter Notebook để xem biểu đồ hội tụ:
# macro_traffic_crawler/02_calibration/calibrate_bpr_optuna.ipynb
```

<!--
### Giai đoạn 3: Phân tích Động lực học Mạng lưới (Tùy chọn)
> **Ghi chú:** Module này được thiết kế tự chứa trong `03_dynamics_analysis/`. Nếu bạn không muốn sử dụng phân tích này trong luận văn, bạn có thể xóa toàn bộ thư mục `03_dynamics_analysis/` mà không gây ảnh hưởng đến các module khác.
```bash
python macro_traffic_crawler/03_dynamics_analysis/traffic_dynamics_analyzer.py
```
-->

### Giai đoạn 3: Cầu nối SUMO & Thẩm định GEH
```bash
# 1. Sinh tệp đếm xe mục tiêu chuẩn SUMO từ dữ liệu TomTom (quy đổi PCU & Modal Split xe máy)
python macro_traffic_crawler/04_sumo_bridge/generate_sumo_counts.py \
    --input macro_traffic_crawler/data/processed/data_hcmc_20_10.csv \
    --output sumo_scenarios/q1_20261020_6h/edge_counts_20261020_6h.xml \
    --start-time 10:31 --end-time 16:48 --alpha 0.61 --beta 2.29

# 2. Đánh giá và xuất báo cáo kiểm chuẩn GEH (UK DMRB) sau khi chạy SUMO
python macro_traffic_crawler/04_sumo_bridge/evaluate_simulation_geh.py
```
