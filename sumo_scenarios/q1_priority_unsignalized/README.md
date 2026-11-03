# Kịch Bản SUMO Không Đèn Tín Hiệu (Unsignalized Priority Scenario)

Kịch bản này chuyển toàn bộ 35 nút giao đèn tín hiệu sang cơ chế nút ưu tiên (Priority Junctions) tuân theo quyền ưu tiên hình học và cấp đường TCVN 104:2007.

## Cấu trúc kịch bản:
- `q1_map_priority.net.xml`: Mạng lưới không đèn tín hiệu.
- `simulation.sumocfg`: Cấu hình chạy mô phỏng chính.
- `simulation_edgedata_priority.xml`: Kết quả vận tốc và lưu lượng từng cạnh sau khi chạy.
- `tripinfo_priority.xml`: Thống kê hành trình và độ trễ của từng phương tiện.

## Hướng dẫn chạy:
1. Quan sát trực quan bằng giao diện GUI:
   ```bash
   sumo-gui -c simulation.sumocfg
   ```
2. Chạy ngầm tốc độ cao (Headless):
   ```bash
   sumo -c simulation.sumocfg
   ```
