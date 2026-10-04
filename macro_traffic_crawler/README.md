# Macro Traffic Crawler & Storage Module

Thư mục con này được thiết kế để **thu thập (crawl)**, **lưu trữ (raw & processed)** dữ liệu giao thông vĩ mô (Macro Traffic Data) từ **TomTom Traffic Flow API**, làm tiền đề để chuyển đổi sang dữ liệu vi mô (Micro Simulation Demand cho SUMO/CityFlow) phục vụ bài toán **Multi-Agent Traffic Signal Control (MARL-TSC)**.

---

## 📁 Cấu trúc thư mục

```text
macro_traffic_crawler/
├── .env.example              # Mẫu cấu hình API key và tham số crawl
├── config.py                 # File cấu hình trung tâm (bounding box, URL, paths)
├── requirements.txt          # Các thư viện phụ thuộc (requests, pandas, python-dotenv)
├── extract_osm_points.py     # Trích xuất tọa độ các trục đường chính từ data/raw_data/map.osm
├── tomtom_client.py          # TomTom Traffic Flow API Client (hỗ trợ retry, rate-limit & mock mode)
├── run_crawler.py            # Script chạy thu thập snapshot hoặc chạy định kỳ
├── data/
│   ├── sampling_points.csv   # Danh sách các điểm đo tọa độ (trích xuất từ mạng lưới đường)
│   ├── raw/                  # Lưu trữ nguyên vẹn snapshot JSON theo timestamp (YYYYMMDD_HHMMSS)
│   └── processed/            # Bảng tổng hợp macro_traffic_history.csv chuẩn hóa phục vụ phân tích
└── README.md                 # Tài liệu hướng dẫn
```

---

## 🚀 Hướng dẫn sử dụng

### Bước 1: Cài đặt thư viện
```bash
cd macro_traffic_crawler
pip install -r requirements.txt
```

### Bước 2: Cấu hình TomTom API Key
Tạo file `.env` từ `.env.example`:
```bash
cp .env.example .env
```
Mở `.env` và điền API key miễn phí từ [TomTom Developer Portal](https://developer.tomtom.com):
```env
TOMTOM_API_KEY=YOUR_ACTUAL_TOMTOM_API_KEY
CRAWL_INTERVAL_SECONDS=300
REQUEST_DELAY_SECONDS=0.2
```
*(Nếu chưa có API key ngay, hệ thống tự động chạy chế độ Mock Test để bạn thử nghiệm pipeline).*

### Bước 3: Tạo danh sách điểm đo từ mạng lưới OSM hiện tại
Chạy script sau để tự động lấy tọa độ các tuyến đường chính (Nguyễn Văn Cừ, Trần Hưng Đạo, Võ Văn Kiệt...) từ `data/raw_data/map.osm`:
```bash
python extract_osm_points.py
```
Kết quả được lưu vào `data/sampling_points.csv`.

### Bước 4: Chạy thu thập dữ liệu Macro
- **Chạy 1 lần (Snapshot test)**:
  ```bash
  python run_crawler.py --limit 10
  ```
- **Chạy vòng lặp định kỳ (cứ mỗi 5 phút/lần thu thập)**:
  ```bash
  python run_crawler.py --mode loop --interval 300 --limit 20
  ```
- **Chạy thử nghiệm không tốn API quota (Mock data)**:
  ```bash
  python run_crawler.py --mock --limit 5
  ```

---

## 📊 Cấu trúc dữ liệu Macro lưu trữ (`macro_traffic_history.csv`)

| Tên cột | Đơn vị | Ý nghĩa | Ứng dụng sang Micro Simulation |
| :--- | :--- | :--- | :--- |
| `timestamp` | ISO-8601 | Thời điểm đo | Phân loại khung giờ cao điểm / thấp điểm |
| `point_id` | String | ID của đoạn đường OSM (`way_xxxx`) | Ánh xạ với `edge_id` trong SUMO `my_network.net.xml` |
| `road_name` | String | Tên đường | Xác định trục giao thông chính |
| `highway_type` | String | Cấp đường (primary, secondary...) | Gán năng lực thông hành làn đường ($C$) |
| `current_speed_kmh` | km/h | Vận tốc thực tế hiện tại ($V_{curr}$) | Tham số kiểm chứng tốc độ phương tiện trong SUMO |
| `free_flow_speed_kmh` | km/h | Vận tốc thiết kế dòng tự do ($V_0$) | Thiết lập `speed` tối đa cho đoạn đường (`net.xml`) |
| `current_travel_time_s` | giây | Thời gian xe đi qua đoạn đường ($T$) | Dùng cho hàm BPR |
| `free_flow_travel_time_s` | giây | Thời gian qua đoạn đường khi vắng ($T_0$) | Thời gian chuẩn không tắc |
| `delay_s` | giây | Độ trễ do ùn tắc ($T - T_0$) | Đánh giá mức độ nghẽn |
| `congestion_index` | 0.0 - 1.0 | Tỉ lệ giảm tốc độ so với tự do | Trọng số phân bổ lưu lượng mạng lưới |
| `est_volume_vph` | xe/giờ | Lưu lượng xe ước tính qua hàm BPR ($V$) | **Đầu vào cốt lõi để sinh số lượng xe** |
| `arrival_rate_vps` | xe/giây | Tần suất xuất hiện xe ($\lambda = V / 3600$) | **Tham số Poisson để sinh vehicle flows vào SUMO** |

---

## 🔄 Cầu nối tiếp theo: Macro sang Micro (SUMO / CityFlow)

Từ bảng dữ liệu macro trên, bước micro hóa tiếp theo sẽ thực hiện:
1. **Lấy `point_id`** map với `edge id` trong `my_network.net.xml`.
2. **Dùng `arrival_rate_vps` ($\lambda$)** để sinh các dòng xe ngẫu nhiên vào mạng lưới bằng `randomTrips.py` hoặc tạo file `my_flow.rou.xml`:
   ```xml
   <flow id="flow_nguyen_van_cu" begin="0" end="3600" vehsPerHour="2176" from="edge_in" to="edge_out"/>
   ```
3. Chạy `tools/converter_v2.py` để chuyển đổi sang `flow.json` và `roadnet.json` cho mô phỏng RL trên CityFlow.
