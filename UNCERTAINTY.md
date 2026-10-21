# Uncertainty: sự cố ngẫu nhiên trên mạng Quận 1

Script `scripsts/run_uncertainty.py` chạy mô phỏng SUMO và chèn thêm các sự cố ngẫu nhiên
(uncertainty), sau đó so sánh với kịch bản không có sự cố (baseline).

## Ba loại sự cố

| Màu chấm | Loại | Mô tả |
|---|---|---|
| Đỏ | `breakdown` | Một xe chết máy hoặc tai nạn đứng yên giữa làn. `--block full` chắn hẳn làn, `--block partial` xe máy vẫn luồn qua được |
| Cam | `closure` | Đóng một làn, cấm xe con, xe máy và xe buýt. Đường chỉ có 1 làn thì là đóng cả đường |
| Vàng | `slow` | Giảm tốc độ tối đa của cả đoạn đường xuống 1.5 đến 4 m/s |

`--kind mixed` chọn ngẫu nhiên một trong ba loại cho mỗi sự cố.

Mỗi sự cố bắt đầu ngẫu nhiên trong khoảng từ giây 300 đến (`--end` trừ 300) và kéo dài 120 đến 600 giây.
Vị trí được chọn theo lưu lượng xe trong `calibrated_routes.rou.xml`.
Cùng một seed thì cho cùng một bộ sự cố.

## Cách chạy

Chạy từ thư mục gốc của dự án.

Xem trực quan (cửa sổ SUMO tự mở, có chấm màu tại vị trí sự cố):

```
python scripsts/run_uncertainty.py --gui --seeds 1 --events 5 --kind mixed --reroute --end 1800
```

Chạy lấy số liệu (không giao diện, có baseline để so sánh):

```
python scripsts/run_uncertainty.py --baseline --seeds 1 2 3 --events 5 --kind mixed --reroute
```

Chỉ xem một loại sự cố: đổi `--kind` thành `breakdown`, `closure` hoặc `slow`.

## Tham số chính

| Tham số | Ý nghĩa | Mặc định |
|---|---|---|
| `--events` | số sự cố mỗi lần chạy | 5 |
| `--kind` | breakdown, closure, slow hoặc mixed | mixed |
| `--seeds` | danh sách seed | 1 |
| `--end` | thời điểm kết thúc (giây) | 1800 |
| `--scale` | hệ số tải xe | 0.05 |
| `--baseline` | chạy thêm kịch bản không sự cố | tắt |
| `--reroute` | xe tự đổi đường, nên dùng cho cả baseline | tắt |
| `--gui` | mở cửa sổ SUMO, tự vẽ chấm màu | tắt |

Lưu ý: `--scale 1.0` là tải gốc đã hiệu chuẩn nhưng mạng bị kẹt cứng (xe liên tục bị teleport),
nên mặc định dùng 0.05.

## Kết quả

Mỗi lần chạy tạo thư mục `results_uncertainty/<kind>_seed<N>/` gồm:
- `events.csv`: danh sách sự cố (loại, ID cạnh, làn, thời điểm bắt đầu, thời gian kéo dài)
- `tripinfo.xml` và `summary.xml`: dữ liệu thô của SUMO

Số liệu tổng hợp được nối vào `results_uncertainty/results.csv` và in ra terminal.
Các cột: `arrived`, `waiting_end`, `mean_duration`, `mean_waiting`, `mean_time_loss`,
`mean_speed`, `teleports`, `collisions`, `dropped`.
Khi có baseline, mỗi chỉ số kèm phần trăm thay đổi so với baseline.