# ĐÁNH GIÁ VÀ KIỂM CHUẨN MÔI TRƯỜNG MÔ PHỎNG VI MÔ TRÊN MÔI TRƯỜNG SUMO
<!--
LỰA CHỌN KHUNG TOÁN HỌC NÀO ĐỂ PHÙ HỢP CHO BÀI TOÁN REINFORCE LEARNING.

-->
## I. Mục tiêu

**1. Tính chân thực của dòng giao thông (Sim-to-Real-Validatity)**: Dòng xe vi mô được tái lập có tái lập đúng lưu lượng, vận tốc, thời gian trể từ  TOMTOM, hành vi xe máy trong giao thông hỗn hợp.

**Tính khả thi của môi trường điều khiển (MARL Environment Sanity)**: Đảm bảo được tính ổn định theo khung Dec-POMDP, không bị artificial deadlock, hành động của tác tử có chi phối được trạng thái giao thông không.

## II. Phương pháp tiến hành
1. Lưu lượng & nhu cầu vi mỗ (flow & demand routing calibration)
2. Động lực vận tốc và hành trình (Speed & time travel accuracy)
3. Động lực tại nút giao thông (intersection & queue dynamics)
4. Kiểm định môi trường MARL DEC- POMDP 

<!--
Đối với các phương pháp tiến hành, xây dựng lên 1 outliner chung để phân tích các phương pháp. 
- Phương pháp đo cái gì ? 
- Dựa trên công thức nào ? 
- Tiêu chuẩn đo của nó 
- Tại sao lại chọn phương pháp đó ? 
- ưu điểm của phương pháp này ? 
- hạn chế của phương pháp này ? 
- kết quả của phương pháp này đo trên bộ dữ liệu của của mình. Chưa chắc chắn chốt bộ dữ liệu này nhưng vẫn sẽ có đánh giá = file ipynb 
- đánh dấu nguồn, thêm nguồn của phương pháp này dựa trên các công trình được published.
-->

### 1. Lưu lượng & nhu cầu vi mỗ (flow & demand routing calibration)
Phương pháp này sẽ độ sự khai khác giữa lưu lượng xe mục tiêu(V_target được suy ra từ nghịch đảo của hàm BPR và dữ liệu của TOMTOM) với lưu lượng xe chạy thực tế qua các cạnh trong SUMO.
Đây là kiểm định phi thống kê phi tham số dựa trên phân phối poisson của dòng xe.

**1.1 Thống kê GEH (Geoffrey E. Havers Statistic)**

**Phương pháp đo:**  
Đo lường mức độ sai lệch giữa lưu lượng giao thông mục tiêu ($V_{\text{target}}$, suy ra từ dữ liệu TomTom qua hàm BPR nghịch đảo) và lưu lượng mô phỏng thực tế chạy qua từng cạnh trong SUMO ($V_{\text{SUMO}}$). Đây là kiểm định thống kê phi tham số dựa trên phân phối Poisson của dòng xe.

**Dựa trên công thức nào**  
Công thức chuẩn được đề xuất bởi Geoffrey E. Havers (1970) và chuẩn hóa trong *UK DMRB Volume 12, Section 2* [2]:

$$GEH_e = \sqrt{\frac{2 \left( V_{\text{SUMO}, e} - V_{\text{target}, e} \right)^2}{V_{\text{SUMO}, e} + V_{\text{target}, e}}}$$

*Trong đó:*
* $V_{\text{SUMO}, e}$: Lưu lượng xe mô phỏng trung bình giờ chạy qua cạnh $e$ trong SUMO $[\text{veh/h}]$.
* $V_{\text{target}, e}$: Lưu lượng xe mục tiêu trung bình giờ trên cạnh $e$ suy ra từ TomTom qua hàm BPR nghịch đảo $[\text{veh/h}]$.
* $GEH_e$: Giá trị thống kê GEH của cạnh $e$ (Đại lượng không thứ nguyên - dimensionless). Mẫu số $\sqrt{V_{\text{SUMO}} + V_{\text{target}}}$ đóng vai trò chuẩn hóa phương sai của quá trình ngẫu nhiên Poisson.

**Tiêu chuẩn đánh giá**
+ GEH < 5.0 : Khớp (FHWA >= 85% số cạnh đo đạt mốc này)

+ 5.0<= GEH < 10.0: Sai lệch ở mức trung bình, chấp nhận được các các nút giao thông phức tạp

+ GEH >= 10: Mô hình phân bổ tuyến đường hoặc dung lượng tuyến có sai số lớn.

**Tiêu chuẩn đánh giá toàn mạng:**

+ GEH < 5.0 : >= 85% tổng số điểm đo toàn mạng.

+ 5.0<= GEH < 10.0: Tối đa dưới 15% tổng số điểm đo.

+ GEH >= 10: 0 hoặc dưới 5%

**Lí do chọn phương pháp:**

Tính bắt buộc pháp lý: Mọi nghiên cứu mô phỏng giao thông được công bố trên các tạp chí vận tải uy tín (IEEE T-ITS, TRB, Transportation Research Part C) đều xem GEH là thước đo bắt buộc để nghiệm thu mô hình trước khi thử nghiệm bất kỳ thuật toán điều khiển nào.

**Ưu điểm:**

Khắc phục hoàn toàn độ nhạy thiên lệch quy mô (scale-bias) của sai số phần trăm thông thường.
Có ngưỡng nghiệm thu quốc tế rõ ràng (85% điểm đo <5.0), giúp kết quả nghiên cứu có tính đối chuẩn công bằng.
Nhận diện chính xác từng nút thắt cổ chai cục bộ trên bản đồ (Spatial Pinpointing).

**Hạn chế:**

Chỉ đếm dựa trên số lượng theo giờ/ chu kì. Một mô hình đạt GEH < 5 về Tổng số lượng xe đi qua, nhưng không phát hiện tình trạng rằng xe chạy nhanh hay chậm theo từng chu kì nhỏ hơn. 

**Kết quả tương đối của phương pháp trên bộ dữ liệu**


**1.2 Phân tích tương quan tuyến tính toàn mạng**

**Phương pháp đo **  
Đánh giá mức độ tương quan và xu hướng phân bổ lưu lượng tổng thể trên toàn bộ $N$ cạnh đo của mạng lưới thông qua mô hình hồi quy tuyến tính giữa lưu lượng xe mô phỏng ($V_{\text{SUMO}}$) và lưu lượng xe mục tiêu ($V_{\text{target}}$). Giúp phát hiện xem mô hình có mắc sai số hệ thống toàn cục (phóng đại thừa xe hay thiếu hụt xe trên diện rộng) hay không.

**Công thức**  
Mô hình hồi quy tuyến tính đi qua gốc tọa độ ($V_{\text{SUMO}} = s \cdot V_{\text{target}}$) kết hợp Hệ số xác định $R^2$ theo chuẩn *FHWA-HRT-04-040* [1] và *WisDOT Chapter 4* [7]:

$$\text{Slope } s = \frac{\sum_{e \in \mathcal{E}} V_{\text{target}, e} \cdot V_{\text{SUMO}, e}}{\sum_{e \in \mathcal{E}} V_{\text{target}, e}^2}$$

$$R^2 = 1 - \frac{\sum_{e \in \mathcal{E}} \left( V_{\text{SUMO}, e} - V_{\text{target}, e} \right)^2}{\sum_{e \in \mathcal{E}} \left( V_{\text{target}, e} - \bar{V}_{\text{target}} \right)^2}$$

*Trong đó:*
* $\mathcal{E}$: Tập hợp tất cả các cạnh đo chung trên mạng lưới ($|\mathcal{E}| = 66\text{ cạnh}$).
* $\bar{V}_{\text{target}} = \frac{1}{|\mathcal{E}|} \sum_{e \in \mathcal{E}} V_{\text{target}, e}$: Lưu lượng mục tiêu trung bình toàn mạng $[\text{veh/h}]$.
* $s$ (Slope): Độ dốc của đường hồi quy tuyến tính.
* $R^2$ (Coefficient of Determination): Hệ số xác định, đo tỷ lệ phương sai của dữ liệu mục tiêu được mô hình SUMO giải thích chính xác.

Hệ số tương quan Pearson $\rho$ bổ trợ:
$$\rho = \frac{\sum_{e \in \mathcal{E}} (V_{\text{target}, e} - \bar{V}_{\text{target}})(V_{\text{SUMO}, e} - \bar{V}_{\text{SUMO}})}{\sqrt{\sum_{e \in \mathcal{E}} (V_{\text{target}, e} - \bar{V}_{\text{target}})^2 \sum_{e \in \mathcal{E}} (V_{\text{SUMO}, e} - \bar{V}_{\text{SUMO}})^2}}$$

**Tiêu chuẩn đánh giá**
* **Độ dốc Hồi quy Slope $s$:** Đo độ lệch quy mô tổng thể:
  * $0.90 \le s \le 1.10$: Đạt chuẩn (Sai lệch quy mô toàn cục không vượt quá $\pm 10\%$).
  * $s < 0.90$: Mạng lưới bị thiếu hụt xe toàn cục (Under-simulated).
  * $s > 1.10$: Mạng lưới bị dồn thừa xe toàn cục (Over-simulated).
* **Hệ số Xác định $R^2$:** Đo mức độ giải thích phương sai và phân tán dữ liệu:
  * $R^2 \ge 0.85$: Đạt chuẩn mô phỏng giao thông (mô hình giải thích được $\ge 85\%$ biến thiên lưu lượng).
  * $R^2 < 0.85$: Lưu lượng giữa các cạnh bị phân tán hỗn loạn, chưa đồng bộ.

**Tiêu chuẩn đánh giá toàn mạng:**
* Bắt buộc đồng thời: **$R^2 \ge 0.85$** và **$0.90 \le s \le 1.10$** (*WisDOT 2014, Table 4.1* [7]; *FHWA-HRT-04-040, Section 4.3* [1]).
* Trên biểu đồ phân tán (Scatter Plot), toàn bộ các điểm $(V_{\text{target}}, V_{\text{SUMO}})$ phải phân bố đối xứng bám sát đường lý tưởng $y = x$ ($45^\circ$).

**Lí do chọn phương pháp:**
* GEH chỉ nhìn nhận cục bộ từng cạnh riêng lẻ (Micro-spatial), trong khi $R^2$ và Slope cho cái nhìn **toàn cảnh vĩ mô (Macro View)**. 
* Giúp phát hiện ngay lỗi thiết lập hệ thống: Nếu Slope lệch xa mốc 1.0, nguyên nhân chắc chắn nằm ở khâu vĩ mô (ví dụ: tính sai hệ số quy đổi PCU, hoặc mạng lưới bị nghẽn biên khiến xe không thể tràn vào).

**Ưu điểm:**
* Phân định rõ ràng giữa **Sai số hệ thống (Slope $s \neq 1.0$)** và **Sai số ngẫu nhiên ($R^2$ thấp)**.
* Trực quan hóa cực kỳ trực tiếp qua đồ thị phân tán Scatter Plot, rất thuyết phục khi trình bày bảo vệ trước Hội đồng.

**Hạn chế:**
* Dễ bị đánh lừa bởi các điểm dị biệt (Outliers): Một vài trục chính có lưu lượng cực lớn ($> 10.000\text{ xe/h}$) nếu khớp tốt có thể kéo $R^2$ lên cao, che lấp sai số lớn ở hàng chục cạnh nhỏ. Do đó bắt buộc phải sử dụng song song với GEH.

**Kết quả tương đối của phương pháp trên bộ dữ liệu**

**1.3 Tỉ lệ hoàn thành nhu cầu và tồn đọng tại nguồn/ đích (Network Insertion & Gate Backlog Rate)**

**Phương pháp đo**  
Đo lường tổng số lượng phương tiện được lên lịch sinh ra theo kế hoạch lộ trình (Loaded/Demanded Vehicles) so với số lượng xe thực sự tiến vào được mạng lưới (Inserted Vehicles), số lượng xe bị mắc kẹt ngoài cổng biên (Virtual Waiting Vehicles), và số lượng xe hoàn thành toàn bộ lộ trình đến đích (Arrived Vehicles) trong suốt thời gian mô phỏng.

**Công thức**  
Được trích xuất từ các trường dữ liệu tích lũy vĩ mô trong thẻ `<step>` cuối cùng của tệp `--summary-output` trong SUMO theo chuẩn *ODOT Protocol* [8] và *DLR SUMO* [9]:

$$\text{Tỷ lệ Nạp mạng (Insertion Completion Rate - ICR)} = \frac{N_{\text{inserted}}}{N_{\text{loaded}}} \times 100\% \quad [\%]$$

$$\text{Tỷ lệ Tồn đọng Cửa ngõ (Gate Backlog Ratio - GBR)} = \frac{N_{\text{waiting}}}{N_{\text{loaded}}} \times 100\% \quad [\%]$$

$$\text{Tỷ lệ Hoàn thành Chuyến đi (Trip Completion Rate - TCR)} = \frac{N_{\text{arrived}}}{N_{\text{inserted}}} \times 100\% \quad [\%]$$

*Trong đó:*
* $N_{\text{loaded}}$: Tổng số phương tiện được định nghĩa cần nạp trong tệp lộ trình `.rou.xml`.
* $N_{\text{inserted}}$: Số lượng xe đã thực sự rời điểm xuất phát và lăn bánh vào mạng lưới đường SUMO.
* $N_{\text{waiting}}$ (trường `waiting` trong SUMO summary): Số lượng phương tiện đã đến thời điểm khởi hành nhưng bị nghẽn không thể chui vào mạng lưới do vị trí xuất phát đã kín chỗ.
* $N_{\text{arrived}}$ (trường `ended` trong SUMO summary): Số lượng phương tiện đã hoàn thành lộ trình và rời khỏi mô phỏng thành công.

**Tiêu chuẩn đánh giá**
* **Tỷ lệ Nạp mạng (ICR):**
  * $ICR \ge 95.0\%$: Đạt chuẩn mô phỏng (Dòng xe dự kiến được nạp gần như trọn vẹn vào mô hình).
  * $ICR < 95.0\%$: Cảnh báo nghiêm trọng; có hiện tượng nghẽn cổng biên (Gate Congestion).
* **Tồn đọng Cửa ngõ (GBR):**
  * $GBR < 5.0\%$: Đạt chuẩn (Lượng xe ùn ứ ngoài biên nằm trong ngưỡng kiểm soát).
  * $GBR \ge 5.0\%$: Không đạt; biên mạng lưới bị quá tải.
* **Tỷ lệ Hoàn thành Chuyến đi (TCR):**
  * $TCR \ge 80.0\%$ (đối với kịch bản dài nhiều giờ $\ge 4\text{h}$): Đạt chuẩn (chứng minh mạng lưới có khả năng tự giải tỏa, xe không bị kẹt vĩnh viễn trên đường).

**Tiêu chuẩn đánh giá toàn mạng:**
* Toàn mạng bắt buộc phải đạt đồng thời: **$ICR \ge 95.0\%$** và **$GBR < 5.0\%$** (*Oregon DOT Guidelines, Section 6* [8]).

**Lí do chọn phương pháp:**
* **Chống hiện tượng "Gian lận mô phỏng vô thức" (Unintentional Simulation Bias):** Nếu cửa ngõ biên bị tắc, hàng vạn xe không thể vào mạng lưới được. Kết quả là mạng lưới bên trong lại trở nên thông thoáng giả tạo, dẫn đến vận tốc mô phỏng đo được có vẻ khớp với thực tế một cách ngẫu nhiên. Chỉ số ICR và GBR là "chốt chặn bảo vệ" tính toàn vẹn của mô hình ngay tại cửa ngõ vào.

**Ưu điểm:**
* Đánh giá trực diện tính khả thi của bài toán phân bổ ma trận gốc - đích (OD Matrix) so với năng lực tiếp nhận vật lý của các tuyến đường biên.
* Tính toán cực kỳ nhanh, đọc trực tiếp từ tệp XML summary mà không đòi hỏi khớp nối tọa độ GPS phức tạp.

**Hạn chế:**
* Là chỉ số tích lũy toàn mạng, không định vị được chính xác đoạn đường cửa ngõ cụ thể nào đang bị nghẽn (cần phối hợp xem xét thuộc tính `departDelay` của từng phương tiện hoặc quan sát SUMO-GUI).

**Kết quả tương đối của phương pháp trên bộ dữ liệu**


## References
1. FHWA (2004). Traffic Analysis Toolbox Volume III: Guidelines for Applying Traffic Microsimulation Modeling Software. Publication No. FHWA-HRT-04-040, Federal Highway Administration, U.S. Department of Transportation, Section 4: Model Calibration.

2. UK Highways Agency (1996). Design Manual for Roads and Bridges (DMRB), Volume 12, Section 2, Part 1: Traffic Appraisal of Road Schemes. The Stationery Office, London.

3. Theil, H. (1966). Applied Economic Forecasting. North-Holland Publishing Company, Amsterdam, Chapter 2: Forecast Evaluation and Information Theory, pp. 26–36.

4. Minh, C. C., Sano, K., & Matsumoto, S. (2005). "Maneuvers of Motorcycles in Mixed Traffic Conditions: A Case Study in Vietnam." Journal of the Eastern Asia Society for Transportation Studies, 6, pp. 198–213.

5. Nguyen, L. X., Sano, K., & Tran, T. V. (2018). "Modeling Motorcycle-Dominated Mixed Traffic Flow Using the Sublane Model in SUMO." Transportation Research Procedia, 34, pp. 83–90.

6. Transportation Research Board (TRB) (2010). Highway Capacity Manual (HCM 2010). National Research Council, Washington, D.C., Chapter 18: Signalized Intersections.

7. Wisconsin Department of Transportation (WisDOT) (2014). Traffic Forecasting and Modeling Guidelines: Chapter 4 - Microsimulation Guidelines. State of Wisconsin.

8. Oregon Department of Transportation (ODOT) (2011). Protocol for Vissim and SUMO Simulation. Transportation Planning Analysis Unit (TPAU), Salem, OR.

9. Lopez, P. A., et al. (2018). "Microscopic Traffic Simulation using SUMO." The 21st IEEE International Conference on Intelligent Transportation Systems (ITSC 2018), pp. 2575–2582.
