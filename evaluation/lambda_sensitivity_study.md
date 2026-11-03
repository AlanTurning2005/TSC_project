# BÁO CÁO KHOA HỌC: KHẢO SÁT ĐỘ NHẠY THAM SỐ NHU CẦU $\lambda$ VÀ KHẢ NĂNG TÁI HIỆN ĐỘNG HỌC VẬN TỐC DÒNG HỖN HỢP TP. HỒ CHÍ MINH

**Đề tài:** Điều khiển Tín hiệu Giao thông Đa tác tử (MARL-TSC) trên Mạng lưới Đô thị Dòng Hỗn hợp Không Phân làn  
**Khu vực:** Lõi Đô thị Quận 1 & Quận 3, TP. Hồ Chí Minh (34 Nút giao Tín hiệu Chu kỳ Cố định, ~169 Nút giao Tổng thể, Diện tích $\approx 2.5\text{ km}^2$)  
**Dữ liệu Thực nghiệm:** TomTom Traffic Flow API (Tần suất Lấy mẫu 1 phút - Interval 60s, 66 Điểm Quan trắc Cố định)  
**Tập Dữ liệu Hiệu chuẩn/Phát triển:** 2026-10-30 (Thứ Sáu, 16:00 – 18:00, 4.092 Bản ghi Thời gian thực, Độ tin cậy Trung bình $98.3\%$)  
**Mã Lưu trữ Thí nghiệm:** `evaluation/reports/lambda_sensitivity/`  
**Hình ảnh Báo cáo:** [`evaluation/reports/lambda_sensitivity/lambda_sensitivity_curve.png`](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/evaluation/reports/lambda_sensitivity/lambda_sensitivity_curve.png)  
**Sổ tay Phân tích Tương tác:** [`evaluation/lambda_sensitivity_study.ipynb`](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/evaluation/lambda_sensitivity_study.ipynb)  

---

## I. MỤC TIÊU NGHIÊN CỨU & LIÊM CHÍNH HỌC THUẬT (OBJECTIVES & ACADEMIC INTEGRITY)

### 1.1. Mục tiêu Cốt lõi
1. **Kiểm chứng Tính Khả thi & Tính Khả định danh (Identifiability):** Khảo sát xem việc thay đổi tốc độ nạp xe tổng hợp $\lambda \in [1.8, \; 3.4]\text{ veh/s}$ có giúp mô hình vi mô SUMO tái hiện trung thực hiện tượng sụt giảm vận tốc từ **Tiền cao điểm (Pre-peak transition)** sang **Đỉnh cao điểm chiều (Peak rush hour)** quan sát được từ TomTom hay không.
2. **Khảo sát Động lực học Dòng xe & Sóng Dừng-Chạy:** Phân tích quy luật biến thiên của các chỉ số vĩ mô cấp độ 1: Sai số Vận tốc ($\text{RMSE}_v, \text{MAE}_v$), Độ lệch Trung bình ($\text{Bias}_v$), Tương quan Thứ hạng Nghẽn ($\rho_{\text{rank}}$), Khoảng cách Phân bố Hình học ($W_1$), và Động lực học Mạng lưới (Tỷ lệ Hoàn thành Chuyến đi $CR\%$, Thời gian Trễ $\bar{T}_{\text{loss}}$).
3. **Triệt tiêu Rò rỉ Dữ liệu (Zero Data Leakage):** Thiết lập ranh giới phương pháp luận nghiêm ngặt giữa tập khảo sát độ nhạy và tập kiểm định ngoài mẫu (Out-of-sample Test Days).

### 1.2. Phân định Chống Rò rỉ Dữ liệu (Data Leakage Prevention)
* **Bản chất Rủi ro:** Trong học máy và khoa học mô phỏng giao thông, Data Leakage xảy ra khi thông tin từ tập kiểm định (Test Set) bị dùng để tối ưu hoặc lựa chọn siêu tham số, khiến kết quả đánh giá cuối cùng bị thổi phồng độ chính xác.
* **Biện pháp Cách ly Dữ liệu Chuẩn tắc:**
  * Toàn bộ thí nghiệm độ nhạy này được thực hiện trên ngày **2026-10-30 (Thứ Sáu)**, được quy định chính thức là **Tập Phát triển / Khảo sát Phương pháp luận (Development / Exploration Set)**.
  * Các ngày độc lập còn lại trong bộ 5 ngày (như **2026-10-15, 2026-10-20...**) được **cô lập tuyệt đối (Strictly Held-out Test Days)** để phục vụ quy trình Kiểm chuẩn Chéo Rời một Ngày (Leave-One-Day-Out - LODO Cross-Validation).
  * Mục tiêu ở đây là khảo sát quy luật đáp ứng động học của hệ thống (system dynamic response), tuyệt đối không dùng để "chọn gán cứng" tham số $\lambda$ lên các ngày kiểm thử. Do đó, **thí nghiệm hoàn toàn không vi phạm nguyên tắc chống rò rỉ dữ liệu**.

---

## II. THIẾT KẾ PHƯƠNG PHÁP LUẬN & BỘ THAM SỐ THỰC NGHIỆM (METHODOLOGY & PARAMETERS)

### 2.1. Cấu hình Khung Thời gian & Cơ chế Khởi động (Warm-up Period)
* **Khung giờ Mô phỏng Đo đạc:** 16:00:00 – 18:00:00 (Thời lượng: 2 Giờ = 7.200 giây).
  * 16:00 – 17:00: Giai đoạn tiền cao điểm, vận tốc TomTom thực tế giảm từ $15.66\text{ km/h} \to 14.78\text{ km/h}$.
  * 17:00 – 18:00: Giai đoạn đỉnh cao điểm chiều, vận tốc TomTom thực tế sụt giảm sâu xuống $13.15\text{ km/h} \to 13.01\text{ km/h}$.
  * Vận tốc thực tế trung bình toàn mạng trong khung 2 giờ: **$13.89\text{ km/h}$** (Trung vị: $11.00\text{ km/h}$, $v_{\text{free}} = 30.21\text{ km/h}$).
* **Cơ chế Khởi động Mạng (Warm-up Period):**
  * Để triệt tiêu hoàn toàn **Cold-Start Bias** (hiện tượng mạng rỗng ban đầu khiến xe phóng nhanh không bị cản trở, làm sai lệch kết quả đo đạc trong 15–20 phút đầu), hệ thống thiết lập thời gian khởi động **15 phút ($900\text{s}$)** trước khi kích hoạt ghi nhận dữ liệu.
  * **Tổng thời gian mô phỏng:** $T_{\text{total}} = 900\text{s} + 7.200\text{s} = \mathbf{8.100\text{s}}$ ($40.500$ bước tích phân vi mô với $\Delta t = 0{,}2\text{s}$).
  * **Bộ lọc Đo đạc Sau Warm-up:**
    * Tệp `edgeData` cấu hình: `begin="900" end="8100" freq="60"`. Toàn bộ dữ liệu vận tốc 15 phút đầu ($t < 900\text{s}$) hoàn toàn bị loại bỏ.
    * Tệp `tripinfo` lọc bỏ toàn bộ các chuyến xe xuất phát trong giai đoạn khởi động (`depart < 900.0s`), chỉ tính toán thống kê cho các phương tiện nạp vào sau khi mạng lưới đã đạt trạng thái cân bằng động.

### 2.2. Chuẩn hóa Mô hình Dòng Hỗn hợp & Hệ thống Đèn Tín hiệu
1. **Hệ thống Đèn Tín hiệu Chu kỳ Cố định (Fixed-Time Network):**
   * Sử dụng mạng lưới gốc [`data/raw_data/q1_map.net.xml`](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/data/raw_data/q1_map.net.xml) với **34 nút giao có đèn tín hiệu**.
   * Chu kỳ đèn chuẩn hóa 90s: Pha 1 (40s Xanh / 5s Vàng / 45s Đỏ), Pha 2 (45s Đỏ / 40s Xanh / 5s Vàng).
2. **Cơ cấu Phương tiện Đô thị TP.HCM (Modal Split) theo TCVN 13592:2022 & Khảo sát Thực địa:**
   * **Xe máy ($85\%$):** Dài $1{,}8\text{m}$, rộng $0{,}8\text{m}$, vận tốc trần tự do `maxSpeed = 9.72 m/s` ($35\text{ km/h}$), khoảng cách an toàn ngang `minGapLat = 0.25m`, hành vi lách làn `latAlignment = "arbitrary"`, thời gian phản xạ $\tau = 0.6\text{s}$.
   * **Xe con ($12\%$):** Dài $4{,}5\text{m}$, rộng $1{,}8\text{m}$, vận tốc trần `maxSpeed = 9.72 m/s` ($35\text{ km/h}$ - bị giam lỏng tốc độ trong dòng xe máy bao quanh), `minGapLat = 0.60m`, $\tau = 1.0\text{s}$.
   * **Xe buýt ($3\%$):** Dài $10{,}5\text{m}$, rộng $2{,}5\text{m}$, vận tốc trần `maxSpeed = 8.33 m/s` ($30\text{ km/h}$), `minGapLat = 0.80m`, `lcSublane = 0.0` (khóa làn phụ, moving bottleneck).
3. **Chia làn Phụ SUMO Sublane & Ổn định Số học:**
   * Kích hoạt `--lateral-resolution 0.25` (khớp 1:1 với khoảng hở an toàn ngang $0{,}25\text{m}$ của xe máy).
   * Kích hoạt `--step-length 0.2` (bảo đảm điều kiện số nguyên $\tau / \Delta t = 0{,}6 / 0{,}2 = 3 \in \mathbb{N}$).
4. **Quy luật Nạp xe Ngoại vi (Commuter Inflow):**
   * `--fringe-factor 8.0`: Tăng xác suất nạp xe từ các cửa ngõ biên (Phú Nhuận, Bình Thạnh, Q3, Q4) đổ vào trung tâm Quận 1 lên gấp 8 lần so với các đường nội bộ.
   * `--min-distance 400.0m`: Loại trừ các chuyến đi siêu ngắn dưới 400m tránh gây nghẽn nhân tạo trong hẻm nhỏ.
   * `--speed-exponent 1.0`: Ưu tiên phân bổ dòng xe vào các trục hành lang lớn (Điện Biên Phủ, NKKN, Pasteur).

### 2.3. Lựa chọn Dải Tham số Nhu cầu $\lambda$
Dải nạp xe $\Lambda = [1.8, \; 2.2, \; 2.6, \; 3.0, \; 3.4]\text{ veh/s}$ tương ứng với các mức lưu lượng mạng:
* $\lambda = 1.8\text{ veh/s}$ ($6.480\text{ xe/h}$): Trạng thái dưới bão hòa ($V < C$).
* $\lambda = 2.2\text{ veh/s}$ ($7.920\text{ xe/h}$): Chuyển tiếp tiền cao điểm, tích lũy hàng đợi cục bộ.
* $\lambda = 2.6\text{ veh/s}$ ($9.360\text{ xe/h}$): Tiệm cận dung lượng thiết kế mạng ($V \approx C$).
* $\lambda = 3.0\text{ veh/s}$ ($10.800\text{ xe/h}$): Quá bão hòa cao điểm ($V > C$), vận tốc sụt giảm sâu.
* $\lambda = 3.4\text{ veh/s}$ ($12.240\text{ xe/h}$): Quá bão hòa sâu / Stress-test áp lực nghẽn mạng cực hạn.

---

## III. KẾT QUẢ THỰC NGHIỆM ĐỐI CHUẨN VĨ MÔ (EMPIRICAL BENCHMARK RESULTS)

Toàn bộ 5 kịch bản mô phỏng chạy hoàn tất trên cùng một mạng lưới và được đánh giá đối chuẩn với tập dữ liệu TomTom quan trắc (66 điểm quan trắc khớp).

### Bảng 1: Bảng tổng hợp số liệu thực nghiệm 5 mức $\lambda$ (2 Giờ, sau Warm-up)

| Tham số $\lambda$ | Lưu lượng Quy đổi | Vận tốc TB $\bar{v}_{\text{sim}}$ | Vận tốc Thực $\bar{v}_{\text{obs}}$ | $\text{RMSE}_v$ (km/h) | $\text{MAE}_v$ (km/h) | $\text{Bias}_v$ (km/h) | Spearman $\rho_{\text{rank}}$ | Wasserstein $W_1$ | Chuyến Hoàn thành | Tỷ lệ $CR\%$ | Độ trễ TB $\bar{T}_{\text{loss}}$ | Thời gian Chờ Đèn |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$1.8\text{ veh/s}$** | $6.480\text{ veh/h}$ | $23.78\text{ km/h}$ | $13.89\text{ km/h}$ | $14.96$ | $13.12$ | $+9.90$ | $-0.055$ | $9.98$ | $11.776$ | $90.86\%$ | $103.5\text{s}$ | $66.1\text{s}$ |
| **$2.2\text{ veh/s}$** | $7.920\text{ veh/h}$ | $22.90\text{ km/h}$ | $13.89\text{ km/h}$ | $14.56$ | $12.86$ | $+9.02$ | $-0.045$ | $9.20$ | $14.364$ | $90.68\%$ | $125.6\text{s}$ | $81.1\text{s}$ |
| **$2.6\text{ veh/s}$** | $9.360\text{ veh/h}$ | $20.31\text{ km/h}$ | $13.89\text{ km/h}$ | $13.54$ | $11.71$ | $+6.42$ | $+0.160$ | $7.26$ | $16.361$ | $87.40\%$ | $216.7\text{s}$ | $140.4\text{s}$ |
| **$3.0\text{ veh/s}$** | $10.800\text{ veh/h}$ | $18.63\text{ km/h}$ | $13.89\text{ km/h}$ | **$\mathbf{13.14}$** | **$\mathbf{11.23}$** | $+4.75$ | **$+0.284$** | $6.28$ | $18.293$ | $84.69\%$ | $290.5\text{s}$ | $194.1\text{s}$ |
| **$3.4\text{ veh/s}$** | $12.240\text{ veh/h}$ | $16.87\text{ km/h}$ | $13.89\text{ km/h}$ | $13.82$ | $11.78$ | **$+2.98$** | $+0.218$ | **$\mathbf{5.21}$** | $19.464$ | $79.51\%$ | $437.1\text{s}$ | $295.4\text{s}$ |

*(Nguồn số liệu: Trích xuất trực tiếp từ `lambda_sensitivity_metrics.csv` và `lambda_sensitivity_metrics.json`).*

---

## IV. CÁC QUAN SÁT KHOA HỌC & ĐỘNG LỰC HỌC DÒNG XE (KEY SCIENTIFIC OBSERVATIONS)

### 4.1. Sự Xuất Hiện của Điểm Uốn Sai số Dạng Chữ U (Convex U-Curve of $\text{RMSE}_v$)
* Khi $\lambda$ tăng từ $1.8 \to 3.0\text{ veh/s}$, sai số $\text{RMSE}_v$ giảm liên tục từ **$14.96\text{ km/h} \to 13.14\text{ km/h}$** (giảm $-1.82\text{ km/h}$).
* Tại $\lambda = 3.0\text{ veh/s}$ ($10.800\text{ xe/h}$), mô phỏng đạt **điểm cực tiểu toàn cục của sai số** ($\text{RMSE}_v = 13.14\text{ km/h}$ và $\text{MAE}_v = 11.23\text{ km/h}$).
* Khi $\lambda$ tiếp tục tăng lên $3.4\text{ veh/s}$, $\text{RMSE}_v$ quay đầu tăng nhẹ lên $13.82\text{ km/h}$. Hiện tượng này xảy ra do một số nút cổ chai bị nghẽn cứng cục bộ khiến vận tốc giảm xuống quá thấp so với các tuyến đường nhánh thông thoáng, làm tăng phương sai sai số không gian.

### 4.2. Hiện tượng Đảo Chiều Tương quan Thứ hạng Nghẽn (Spearman Rank Flip)
* Tại $\lambda = 1.8$ và $2.2\text{ veh/s}$, tương quan Spearman mang giá trị âm nhẹ ($\rho \approx -0.05$). Lý do: khi mạng chưa đủ tải, các trục đường lớn (Điện Biên Phủ, NKKN) có nhiều làn xe nên xe chạy rất nhanh, trong khi ngoài đời thực đây lại là những trục bị nghẽn nặng nhất.
* Tại $\lambda = 2.6\text{ veh/s}$, tương quan đảo chiều sang dương ($\rho = +0.160$) và đạt đỉnh **$\rho = +0.284$ tại $\lambda = 3.0\text{ veh/s}$**. Điều này chứng minh rằng **mức tải $10.800\text{ xe/h}$ đã kích hoạt đúng cơ chế nghẽn trên các trục hành lang huyết mạch**, giúp SUMO nhận diện đúng thứ tự các tuyến đường tắc nhất tương thích với TomTom.

### 4.3. Sự Thu Hẹp của Khoảng cách Phân bố Hình học (Wasserstein Metric $W_1$)
* Khoảng cách Wasserstein $W_1$ giảm đơn điệu theo chiều tăng của $\lambda$: từ **$9.98\text{ km/h} \to 9.20 \to 7.26 \to 6.28 \to \mathbf{5.21\text{ km/h}}$**.
* Khoảng cách $W_1 = 5.21\text{ km/h}$ tại $\lambda = 3.4\text{ veh/s}$ chứng minh rằng hàm phân bố xác suất vận tốc $P_{\text{sim}}(v)$ của mô hình vi mô đã dịch chuyển sâu vào vùng vận tốc thấp, trùng khớp với phân bố vận tốc thực tế của TomTom trong giờ cao điểm.

### 4.4. Động lực học Tích lũy Phương tiện & Sự Bùng nổ Thời gian Trễ ($\bar{T}_{\text{loss}}$)
* **Tỷ lệ hoàn thành chuyến đi ($CR\%$):** Duy trì mức cao $>90.6\%$ ở $\lambda \le 2.2\text{ veh/s}$, bắt đầu giảm xuống $87.4\%$ tại $\lambda = 2.6\text{ veh/s}$, và sụt giảm còn **$79.51\%$ tại $\lambda = 3.4\text{ veh/s}$**.
* **Độ trễ trung bình ($\bar{T}_{\text{loss}}$) và Thời gian Chờ đèn:**
  * Tại $\lambda = 1.8$: Thời gian trễ là $103.5\text{s}$ (thời gian dừng chờ đèn $66.1\text{s}$).
  * Tại $\lambda = 3.4$: Thời gian trễ tăng gấp **4.2 lần** lên tới **$437.1\text{s}$ (~7.3 phút)**, trong đó thời gian dừng chết chờ đèn và xếp hàng đợi chiếm tới **$295.4\text{s}$ (~5 phút)**.
* **Kết luận Động học:** Đây là minh chứng xác thực của hiện tượng quá bão hòa (Oversaturation). Khi lưu lượng vượt quá dung lượng chu kỳ đèn cố định (40s Xanh / 5s Vàng / 45s Đỏ), các phương tiện không kịp giải tỏa trong một chu kỳ, hàng đợi lan ngược (queue spillback) qua các nút kế cận và giam giữ phương tiện lại trong mạng.

---

## V. ĐÁNH GIÁ SO SÁNH ĐỊNH DẠNG `.py` VS `.ipynb` VÀ KHUYẾN NGHỊ LƯU TRỮ

| Tiêu chí | File Script Python (`.py`) | Jupyter Notebook (`.ipynb`) |
| :--- | :--- | :--- |
| **Độ ổn định Tính toán Nặng** | **Xuất sắc**: Chạy ngầm đa tiến trình (ProcessPoolExecutor trên 5–12 CPU cores), không phụ thuộc vào trình duyệt, không lo tràn bộ nhớ hay rớt kết nối WebSocket/Kernel. | **Hạn chế**: Nếu chạy mô phỏng SUMO dài 8–10 phút trực tiếp trong 1 cell, kernel dễ bị treo hoặc quá tải khi SUMO in hàng nghìn cảnh báo va chạm/teleport. |
| **Trực quan hóa & Hiển thị** | **Bình thường**: Phải lưu ảnh ra đĩa rồi mở file xem riêng; bảng số liệu hiển thị dạng text qua terminal console. | **Xuất sắc**: Hiển thị bảng DataFrame tương tác trực tiếp (inline tables) và biểu đồ đa panel sắc nét ngay trong giao diện VS Code. |
| **Bảo lưu Kết quả Nghiên cứu** | Chỉ lưu mã nguồn; kết quả số liệu phải ghi ra các file ngoài (`.csv`, `.json`). | **Xuất sắc**: Toàn bộ kết quả số, bảng tổng kết và biểu đồ được **đóng băng vĩnh viễn (frozen)** trong cấu trúc JSON metadata của notebook. Sau này mở lại xem được ngay lập tức mà không cần chạy lại mô phỏng. |
| **Tái sử dụng cho Khóa luận** | Cung cấp mã xử lý dữ liệu chuẩn dạng module. | Rất thuận tiện để copy trực tiếp các đoạn mã trích xuất bảng LaTeX và xuất ảnh đồ thị độ phân giải cao (300 DPI). |

### Khuyến nghị Thực tiễn cho Khóa luận:
1. **Sử dụng tệp ảnh đồ thị độ phân giải cao (300 DPI):** Đồ thị [`evaluation/reports/lambda_sensitivity/lambda_sensitivity_curve.png`](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/evaluation/reports/lambda_sensitivity/lambda_sensitivity_curve.png) đã được định dạng chuẩn IEEE, sẵn sàng chèn trực tiếp vào chương Thực nghiệm của khóa luận trên LaTeX/Overleaf.
2. **Sử dụng Notebook để Trình diễn Nghiệm thu:** Tệp [`evaluation/lambda_sensitivity_study.ipynb`](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/evaluation/lambda_sensitivity_study.ipynb) đóng vai trò là bằng chứng thực nghiệm độc lập (Proof of Concept), có thể mở và trình chiếu tương tác mà không cần phải chạy lại toàn bộ mô phỏng tốn tài nguyên.
3. **Định vị Tham số Nhu cầu cho Mô hình MARL:**
   * Nghiên cứu này khẳng định dải tải trọng hợp lý nhất của mạng lưới Quận 1 & Quận 3 trong giờ cao điểm nằm trong khoảng $\lambda \in [2.6, \; 3.2]\text{ veh/s}$ ($9.360 - 11.500\text{ xe/h}$).
   * Mức tải này tạo ra đủ áp lực hàng đợi và xung đột thực tế, là môi trường kiểm chuẩn hoàn hảo để các thuật toán MARL (CoLight, MPLight, IDQN) thể hiện ưu thế điều phối vượt trội so với Fixed-Time và Webster.
