# Traffic Signal Control (CityFlow to SUMO Pipeline)

Dự án chuyển đổi bản đồ và luồng giao thông từ định dạng CityFlow sang SUMO phục vụ nghiên cứu Multi-Agent Reinforcement Learning (MARL).

## Cấu trúc thư mục
- `data_cityflow/`: Chứa dữ liệu gốc từ CityFlow (`roadnet.json`, `flow.json`).
- `tools/`: Các công cụ chuyển đổi (`converter_v2.py`).
- `sumo_scenarios/`: Kịch bản và mạng lưới SUMO sau khi biên dịch.
- `scripsts/`: Các script thực thi pipeline chuyển đổi và đọc dữ liệu.

## Hướng dẫn chạy

1. **Yêu cầu môi trường:**
   - Python 3.9+
   - SUMO 1.20+ (đã cấu hình biến môi trường `SUMO_HOME`)

2. **Chuyển đổi kịch bản CityFlow sang SUMO:**
   ```bash
   python scripsts/run_convert.py
   ```

3. **Chạy mô phỏng SUMO:**
   - Chạy với giao diện đồ họa:
     ```bash
     sumo-gui -c sumo_scenarios/HZ/simulation.sumocfg
     ```
   - Chạy xuất file thống kê chuyến đi:
     ```bash
     sumo -c sumo_scenarios/HZ/simulation.sumocfg --tripinfo-output sumo_scenarios/HZ/tripinfo.xml
     ```

4. **Đọc kết quả thống kê:**
   ```bash
   python scripsts/read_results.py
   ```