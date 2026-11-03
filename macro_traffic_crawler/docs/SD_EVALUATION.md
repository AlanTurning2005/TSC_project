# KHUNG PHƯƠNG PHÁP LUẬN ĐÁNH GIÁ VÀ HIỆU CHUẨN MÔI TRƯỜNG MÔ PHỎNG VI MÔ DỰA TRÊN DỮ LIỆU TỐC ĐỘ PROBE
## (Speed-Calibrated Heterogeneous Sublane Testbed for MARL Traffic Signal Control)

---

## I. ĐỊNH VỊ ĐỀ TÀI & CƠ SỞ TOÁN HỌC (POSITIONING & MATHEMATICAL FORMULATION)

### 1.1. Định danh và Bản chất của Môi trường Kiểm chuẩn
* **Tên gọi chính thức:** *Speed-Calibrated Heterogeneous Sublane Testbed*.
* **Bản chất nhu cầu giao thông:** Nhu cầu giao thông trong mô hình vi mô SUMO là **Nhu cầu Tổng hợp (Synthetic Demand)**, được hiệu chuẩn theo dữ liệu tốc độ thực nghiệm từ TomTom Traffic Flow API (Endpoint `flowSegmentData`: tốc độ hiện tại $v_{\text{curr}}$, tốc độ tự do $v_{\text{free}}$, thời gian hành trình $t_{\text{travel}}$, độ tin cậy $\text{confidence}$).
* **Liêm chính học thuật (Academic Integrity & Zero Hallucination):** 
  Do khu vực nghiên cứu (Quận 1 & Quận 3, TP.HCM) không có hệ thống camera hay vòng từ đếm xe liên tục phủ kín 66 điểm quan trắc, nghiên cứu **không khẳng định độ chính xác tuyệt đối về số lượng phương tiện thực tế (vehicle counts)**. Mục tiêu cốt lõi của môi trường là:
  1. Tái hiện các **mẫu hình ùn tắc vĩ mô hợp lý (Plausible Congestion Patterns)** và các đợt **sóng dừng-chạy (Stop-and-Go Shockwaves)** tương thích với bức tranh tốc độ quan sát được.
  2. Cung cấp một môi trường thử nghiệm động lực học tương tác phục vụ việc huấn luyện và đánh giá tính bền vững (robustness) của các thuật toán Điều khiển Tín hiệu Giao thông bằng Học tăng cường Đa tác tử (MARL-TSC).

---

### 1.2. Chuẩn hóa Khung Toán học Dec-POMDP với Phần thưởng Cục bộ
Môi trường điều khiển giao thông đa nút tín hiệu được mô hình hóa theo khung **Quá trình Quyết định Markov Phi tập trung, Quan sát một phần với Phần thưởng Cục bộ (Decentralized Partially Observable MDP with Local Rewards / Networked MARL)** [Oliehoek & Amato, 2016]:

$$\mathcal{M} = \langle \mathcal{N}, \mathcal{S}, \{\mathcal{A}_i\}, \mathcal{P}, \{\mathcal{R}_i\}, \{\mathcal{O}_i\}, \gamma_{\text{RL}} \rangle$$

*Trong đó:*
* $\mathcal{N} = \{1, 2, \dots, N\}$: Tập hợp $N = 35$ nút giao điều khiển đèn tín hiệu (các tác tử RL).
* $\mathcal{S}$: Không gian trạng thái toàn cục của mạng lưới (vị trí, vận tốc vi mô, gia tốc của từng phương tiện trong mạng).
* $\mathcal{A}_i$: Không gian hành động của tác tử $i$. $a_i \in \mathcal{A}_i$ biểu diễn việc chọn pha đèn kế tiếp (Phase Selection) hoặc chuyển đổi pha (Phase Switch), tuân thủ ràng buộc an toàn giao thông: thời gian vàng tối thiểu $t_{\text{yellow}} \ge 3\text{s}$ và thời gian xanh tối thiểu $g_{\text{min}} \ge 10\text{s}$.
* $\mathcal{P}(s' \mid s, \mathbf{a})$: Xác suất chuyển dịch trạng thái toàn cục khi các tác tử thực thi đồng thời hành động liên hợp $\mathbf{a} = (a_1, \dots, a_N)$, được chi phối bởi bộ giả lập vi mô SUMO.
* $\mathcal{O}_i$: Không gian quan sát cục bộ của tác tử $i$, trích xuất từ các đoạn đường nhập nút (incoming edges):
  $$o_i = [q_i, d_i, k_i, p_i, w_i]$$
  * $q_i$: Chiều dài hàng đợi tích lũy (queue length) trên từng làn tiếp cận nút [m hoặc số xe].
  * $d_i$: Thời gian trễ trung bình của các phương tiện tiếp cận nút [s].
  * $k_i$: Mật độ phương tiện trên các cạnh nhập nút [veh/km].
  * $p_i$: Áp lực nút giao (Pressure) theo lý thuyết Max-Pressure [Varaiya, 2013]: chênh lệch số lượng xe giữa các làn nhập và làn xuất tương ứng.
  * $w_i$: Pha đèn hiện tại và thời gian pha đã trôi qua.
* $\mathcal{R}_i$: Hàm phần thưởng cục bộ của tác tử $i$, được thiết kế dạng hàm lồi phạt hàng đợi dài và áp lực nút nhằm tránh hiện tượng phần thưởng thưa thớt (Sparse Reward):
  $$r_i(s, \mathbf{a}) = - \left( \sum_{l \in \mathcal{L}_{\text{in}, i}} q_l^2 + w_{\text{delay}} \sum_{l \in \mathcal{L}_{\text{in}, i}} d_l + w_{\text{press}} |p_i| \right)$$
* $\gamma_{\text{RL}} \in [0{,}95, \; 0{,}99]$: Hệ số chiết khấu phần thưởng theo thời gian của tác tử RL.

---

### 1.3. Mô hình Dòng Hỗn hợp Đa phương tiện Không phân làn (Heterogeneous Sublane Model)
Đặc thù giao thông đô thị Việt Nam là dòng hỗn hợp không tuân thủ làn cứng, xe máy chiếm tỷ trọng áp đảo và có hành vi lách làn linh hoạt [Minh et al., 2005]. Mô hình áp dụng kỹ thuật chia làn phụ (Sublane Model) chính thức của SUMO [Erdmann, 2015] chuẩn hóa theo tài liệu kỹ thuật của đề tài (`HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md`):
* **Cấu hình Chia làn phụ:** Kích hoạt tham số `--lateral-resolution 0.25` (chia mỗi làn vật lý thành các dải không gian nhỏ $0{,}25\text{m}$, khớp 1:1 với khoảng cách an toàn ngang `minGapLat = 0.25m` của xe máy).
* **Bước Tích phân Thời gian:** Thiết lập `--step-length 0.2` để tỷ số giữa thời gian phản xạ người lái và bước tích phân là số nguyên ($\tau / \Delta t = 0{,}6 / 0{,}2 = 3 \in \mathbb{N}$), triệt tiêu lỗi trôi số học vi mô.
* **Cấu trúc Phương tiện Thiết kế (Chuẩn hóa Học thuật):**
  * Xe máy (Motorcycles - $85\%$): Kích thước $1{,}8\text{m} \times 0{,}8\text{m}$, vận tốc trần tự do `maxSpeed = 9.72 m/s` ($35\text{ km/h}$ - neo theo $v_{\text{free}}$ TomTom), gia tốc $1{,}5\text{ m/s}^2$, giảm tốc $2{,}0\text{ m/s}^2$, `minGapLat = 0.25m`, `latAlignment="arbitrary"`.
  * Xe con (Passenger Cars - $12\%$): Kích thước $4{,}5\text{m} \times 1{,}8\text{m}$, vận tốc trần `maxSpeed = 9.72 m/s` ($35\text{ km/h}$ - giam lỏng tốc độ trong dòng xe máy), gia tốc $1{,}8\text{ m/s}^2$, giảm tốc $3{,}0\text{ m/s}^2$, `minGapLat = 0.60m`, `latAlignment="center"`.
  * Xe buýt (Buses - $3\%$): Kích thước $10{,}5\text{m} \times 2{,}5\text{m}$, vận tốc trần `maxSpeed = 8.33 m/s` ($30\text{ km/h}$), gia tốc $1{,}0\text{ m/s}^2$, giảm tốc $2{,}0\text{ m/s}^2$, `minGapLat = 0.80m`, `lcSublane = 0.0` (khóa làn phụ, moving bottleneck).
* **Ghi chú Minh bạch về Số liệu:**
  Tỷ lệ phương tiện $85\%$ xe máy, $12\%$ ô tô con, $3\%$ xe buýt được đối chiếu trực tiếp từ khảo sát thực địa tại TP.HCM của Dung et al. (2015) và quy chuẩn mặt cắt ngang TCVN 13592:2022.

---

### 1.4. Quy chuẩn Sinh Tuyến đường & Nhu cầu Tổng hợp (Synthetic Demand Generation Protocol)
Để khắc phục hoàn toàn hiện tượng bùng nổ lưu lượng do nghịch đảo công thức BPR (vốn từng tạo ra tới 798.492 xe trong 6h gây nghẽn cứng mạng), quy trình sinh tuyến đường tổng hợp được chuẩn hóa bằng công cụ `randomTrips.py` kết hợp giải thuật định tuyến Dijkstra thích ứng `duarouter` với bộ tham số thực nghiệm:

* **Tập trung Luồng Nạp Ngoại vi (`--fringe-factor 8.0`):**
  * *Bản chất giao thông:* Khu vực trung tâm Quận 1 và Quận 3 đóng vai trò là cực thu hút và thông hành (commuter & through-traffic core). Dòng xe vào giờ cao điểm chủ yếu bắt nguồn từ các quận vành đai (Bình Thạnh, Phú Nhuận, Quận 4, TP. Thủ Đức, Tân Bình) đổ vào các trục đại lộ chính (Điện Biên Phủ, Nam Kỳ Khởi Nghĩa, Pasteur, Hai Bà Trưng).
  * *Ý nghĩa tham số:* Thiết lập hệ số `fringe-factor = 8.0` làm tăng xác suất xuất phát và kết thúc chuyến đi tại các cạnh biên lên gấp **8 lần** so với các cạnh nội bộ. Thiết lập này ngăn chặn hiện tượng sinh xe giả tạo từ giữa các con hẻm nhỏ hoặc các đoạn đường ngắn trong lõi, phản ánh đúng đặc tính dòng hành trình xuyên tâm (through-trips).
* **Khoảng cách Chuyến đi Tối thiểu (`--min-distance 400.0` m):**
  * *Khắc phục sai số vi mô:* Trong lưới đường đô thị dày đặc, các chuyến đi ngẫu nhiên dưới 400m sẽ tạo ra các phương tiện vừa xuất hiện đã rẽ ngay tại góc cua kế tiếp, gây xung đột và tắc nghẽn cục bộ nhân tạo mà không tham gia vào động lực học hành lang chính.
  * *Ý nghĩa:* Ràng buộc chuyến đi dài tối thiểu 400m buộc các phương tiện phải lưu thông qua ít nhất 2 đến 4 nút giao tín hiệu, bảo đảm dữ liệu vận tốc phản ánh đúng tính chất chuỗi hành trình đô thị.
* **Định tuyến Ưu tiên Cấp đường (`--speed-exponent 1.0`):**
  * Trọng số lựa chọn tuyến đường trong `duarouter` được lũy thừa theo tốc độ tối đa của cạnh, hướng dòng xe ưu tiên lưu thông trên các trục đường trục chính (Arterials) thay vì đi tắt qua các tuyến đường dân sinh hẹp.
* **Loại bỏ Vòng lặp (`--validate` & `--remove-loops`):**
  * Triệt tiêu hoàn toàn các lộ trình có vòng xoay khép kín hoặc đảo chiều phi thực tế trước khi nạp vào SUMO.
* **Đồng bộ Bước Thời gian Mô phỏng (`--step-length 0.2` s):**
  * Thời gian phản xạ của xe máy trong dòng hỗn hợp được xác lập thực nghiệm $\tau = 0.6\text{s}$ (Vu & Preston, 2023). Bước mô phỏng vi mô của SUMO bắt buộc phải thiết lập $\Delta t = 0{,}2\text{s}$ để đảm bảo điều kiện ổn định số học $\tau / \Delta t = 0{,}6 / 0{,}2 = 3 \in \mathbb{N}$ (Mục 2.1), triệt tiêu hoàn toàn hiện tượng trễ phản xạ và phanh gián đoạn nhân tạo.

---

## II. CƠ CHẾ SINH NHU CẦU & HIỆU CHUẨN ĐỘNG HỌC $\boldsymbol{\lambda}(t)$

### 2.1. Bản chất Hệ Động Lực & Vấn đề Bất khả Định danh khi Quá bão hòa
* **Hệ thống có trạng thái nhớ (State-Space Dynamic System):** Dòng xe và hàng đợi trong SUMO có tính phụ thuộc thời gian (xe nạp ở khoảng $t-1$ vẫn còn tồn đọng trong mạng ở khoảng $t$). Do đó, việc ước lượng vector nhu cầu $\boldsymbol{\lambda}(t)$ là bài toán **Ước lượng Trạng thái - Tham số Đồng thời (Dual State-Parameter Estimation)**, không thể xem các lát thời gian là độc lập.
* **Vấn đề Tính Bất khả Định danh (Identifiability / Flat Loss Landscape):**
  Khi nhu cầu vượt trần dung lượng ($V > C$), dòng xe rơi vào trạng thái quá bão hòa sâu (Oversaturation): vận tốc sụt giảm về sàn bò ($v \approx 5 - 10\text{ km/h}$) và giữ nguyên ở đó dù nhu cầu thực tế là $1.2 C$ hay $1.8 C$.
  $$\frac{\partial v}{\partial \lambda} \approx 0 \quad (\text{khi } V > C)$$
  Tại vùng này, hàm mất mát tốc độ bị phẳng lì ("censored"). Nhiều giá trị $\lambda$ khác nhau cho cùng một tốc độ sụp đổ, khiến thuật toán tối ưu hóa dễ bị trôi dạt (drift) nếu không có số hạng điều chuẩn ràng buộc.

---

### 2.2. Phương pháp Tối ưu hóa Toàn ngày có Điều chuẩn Trơn (Simultaneous Regularized Optimization)
Để loại trừ hoàn toàn chuỗi sai số tích tụ (Error Compounding) của phương pháp tối ưu tuần tự cắt lát, đề tài áp dụng **Tối ưu hóa Đồng thời Vector Nhu cầu $\boldsymbol{\lambda} \in \mathbb{R}^K$** (với $K \approx 15 - 20$ lát cắt thời gian 30 phút cho kịch bản cả ngày) kết hợp điều chuẩn trơn vi phân bậc hai và hình dạng tiên nghiệm:

$$\min_{\boldsymbol{\lambda}} \mathcal{L}(\boldsymbol{\lambda}) = \text{RMSE}_v(\boldsymbol{\lambda}) + \gamma_{\text{smooth}} \sum_{k=2}^{K-1} (\lambda_{k+1} - 2\lambda_k + \lambda_{k-1})^2 + \gamma_{\text{prior}} \|\boldsymbol{\lambda} - \boldsymbol{\lambda}_{\text{prior}}\|^2 + w_{\text{pen}} \cdot \mathcal{P}_{\text{BPR}}^{\text{norm}}(\boldsymbol{\lambda})$$

*Trong đó:*
1. **$\text{RMSE}_v(\boldsymbol{\lambda})$:** Sai số bình phương trung bình giữa vận tốc mô phỏng và vận tốc TomTom trên toàn bộ cửa sổ mô phỏng liền mạch.
2. **Số hạng Điều chuẩn Trơn $\sum (\lambda_{k+1} - 2\lambda_k + \lambda_{k-1})^2$:** Ràng buộc vi phân bậc hai ép đường cong nhu cầu phát sinh phải biến thiên mượt mà, loại trừ hiện tượng $\lambda$ dao động răng cưa phi vật lý giữa các lát cắt.
3. **Số hạng Tiên nghiệm $\|\boldsymbol{\lambda} - \boldsymbol{\lambda}_{\text{prior}}\|^2$:** Khóa hình dạng đường cong nhu cầu theo tỷ lệ biến thiên giờ cao điểm/thấp điểm trích xuất từ nghiên cứu HOUTRANS TP.HCM, giải quyết triệt để tính bất khả định danh khi đường bị kẹt cứng ($V > C$).
4. **Nhu cầu Liên tục (Continuous Demand Flow):** Thay vì nạp xe nhảy bậc vuông (gây sốc tải nhân tạo), vector $\boldsymbol{\lambda}$ được nội suy thành hàm **tuyến tính từng khúc (Piecewise Linear)** hoặc **B-spline** khi truyền vào SUMO.
5. **Thuật toán giải:** Giải bằng **Coordinate Descent** hoặc **CMA-ES** (Covariance Matrix Adaptation Evolution Strategy) với 10–20 tham số.

*(Lưu ý về phương án dự phòng: Nếu bị giới hạn tài nguyên tính toán, áp dụng Fixed-Lag Smoothing 2 bước liên tiếp kết hợp tính năng lưu/nạp trạng thái `--save-state` và `--load-state` của SUMO để không phải chạy lại từ $t=0$).*

---

### 2.3. Rào chắn Dung sai Mềm BPR & Định lượng Khoa học cho $w_{\text{pen}}$

#### Chuẩn hóa Phi Thứ nguyên:
Hàm phạt vi phạm dải BPR $[\underline{V}_e, \bar{V}_e]$ được chuẩn hóa theo tỷ số vi phạm tương đối bình phương ($\delta^2$) chia cho dung lượng thiết kế $C_e^2$:

$$\mathcal{P}_{\text{BPR}}^{\text{norm}}(\boldsymbol{\lambda}) = \frac{1}{|\mathcal{E}|} \sum_{e \in \mathcal{E}} \left[ \left( \frac{\max(0, \; \underline{V}_e - V_{\text{sim}, e}(\boldsymbol{\lambda}))}{C_e} \right)^2 + \left( \frac{\max(0, \; V_{\text{sim}, e}(\boldsymbol{\lambda}) - \bar{V}_e)}{C_e} \right)^2 \right]$$

Lúc này, đại lượng $\mathcal{P}_{\text{BPR}}^{\text{norm}}$ là một số thực không thứ nguyên (ví dụ vi phạm $20\%$ dung lượng $\implies \delta^2 = (0.2)^2 = 0.04$). Do $\text{RMSE}_v$ có đơn vị là $\text{km/h}$, hệ số phạt $w_{\text{pen}}$ bắt buộc phải mang đơn vị là **$\text{km/h}$**.

#### Quy trình 2 Bước Xử lý $w_{\text{pen}}$:
1. **Bước 1 - Kiểm tra Khả thi Tiên nghiệm (A Priori Check):**
   Chạy tối ưu hóa $\boldsymbol{\lambda}^*$ thuần túy theo $\text{RMSE}_v$ (với $w_{\text{pen}} = 0$). 
   *Nếu $V_{\text{sim}, e}$ tự nhiên nằm trọn trong dải dung lượng hợp lý ($\mathcal{P}_{\text{BPR}} = 0$):* Chuyển BPR thành một chỉ số hậu kiểm (A posteriori Sanity Metric), **loại bỏ hoàn toàn $w_{\text{pen}}$ khỏi hàm mục tiêu**, giúp lược bỏ một siêu tham số gây tranh cãi.
2. **Bước 2 - Định lượng $w_{\text{pen}}$ theo Sàn Nhiễu (nếu có vi phạm $\mathcal{P} > 0$):**
   Nếu xuất hiện vi phạm vượt trần vật lý, $w_{\text{pen}}$ được định lượng sao cho mức vi phạm nghiêm trọng $\delta^* = 0.20$ ($20\% C$) sẽ bị phạt một lượng ngang bằng với Sàn nhiễu tự nhiên của dữ liệu $\Delta_{\text{noise}}$:
   $$w_{\text{pen}} = \frac{\Delta_{\text{noise}}}{(\delta^*)^2} \quad [\text{km/h}]$$
   *(Ví dụ: Với $\Delta_{\text{noise}} \approx 2.5\text{ km/h}$ và $\delta^* = 0.20$, $w_{\text{pen}} = \frac{2.5}{0.04} \approx 62.5\text{ km/h}$. Mức phạt này đủ mạnh để ngăn chặn bộ tối ưu hóa đánh đổi dung lượng lấy sai số tốc độ).*

---

### 2.4. Giả thuyết Nghiên cứu về Hiện tượng Quá Bão Hòa ($H_{\text{oversat}}$)
Trong giao thông hỗn hợp tại TP.HCM, quy chuẩn thiết kế đường bộ cũ (TCVN) thường ước tính dung lượng xe máy dựa trên hệ số quy đổi tĩnh ($PCU = 0.3$), chưa phản ánh hết khả năng điền đầy mật độ cao (Jam Density $k_{\text{jam}} \approx 300 - 400\text{ xe máy/km/làn}$).

> ### Giả thuyết Khoa học $H_{\text{oversat}}$:
> *"Tại các trục hành lang huyết mạch khu vực Quận 1 và Quận 3 (Nam Kỳ Khởi Nghĩa, Hai Bà Trưng, Pasteur, CMT8) trong khung giờ cao điểm (07:15 – 08:30), nhu cầu giao thông thực tế đã vượt trần dung lượng thiết kế TCVN ($V/C > 1.0$). Tình trạng quá bão hòa này là nguyên nhân chính dẫn đến hiện tượng vận tốc sụt giảm về sàn bò ($v \le 10\text{ km/h}$) và hàng đợi tràn nút."*

* **Ý nghĩa:** Cận trên $\bar{V}_e$ của dải BPR mềm được thiết lập chủ động cho phép $V/C \in [1.2, \; 1.5]$ để kiểm chứng giả thuyết này, chỉ chặn các giá trị vô lý về mặt kích thước hình học (như $> 10.000\text{ xe/h/làn}$).

---

## III. QUY TRÌNH THU THẬP DỮ LIỆU & XỬ LÝ NHIỄU CONFIDENCE

### 3.1. Bản chất TomTom Confidence & Phòng ngừa Rò rỉ Thông tin
* **Cơ chế API TomTom:** Khi mật độ thiết bị probe thời gian thực cao, TomTom trả về `confidence` $\approx 0.8 - 1.0$. Khi ít phương tiện bật định vị (đường hẻm nhỏ hoặc ban đêm), TomTom **tự động fallback về cơ sở dữ liệu tốc độ lịch sử** và hạ thấp `confidence`.
* **Rủi ro rò rỉ:** Dữ liệu có confidence thấp bản chất là dữ liệu lịch sử của TomTom, không phải quan trắc thời gian thực độc lập. Nếu ép dùng dữ liệu này, việc so sánh với Baseline Historical Median sẽ bị sai lệch.

---

### 3.2. Quy trình Lọc & Gán Trọng số Chuẩn tắc
1. **Khảo sát Độ phủ Cạnh $\times$ Giờ (Spatial-Temporal Coverage EDA):**
   * Vẽ biểu đồ nhiệt kiểm tra tỷ lệ đạt confidence theo từng cạnh.
   * **Loại bỏ các cạnh "mù" khỏi $\mathcal{E}_{\text{train}}$:** Các đoạn đường có tỷ lệ bản ghi đạt $c \ge 0.5$ dưới $50\%$ được đánh dấu là "thiếu thông tin probe" và đưa ra khỏi tập hiệu chuẩn, tránh để SUMO học theo dữ liệu lịch sử mặc định của TomTom.
2. **Trọng số Nghịch đảo Phương sai Tối ưu (Inverse Variance Weighting):**
   Áp dụng trọng số Gauss-Markov cho các cạnh còn lại trong hàm mất mát:
   $$w_e(c) = \frac{1}{\hat{\sigma}^2(c)}$$
   Trong đó phương sai đo lường $\hat{\sigma}^2(c)$ được ước lượng thực nghiệm từ độ lệch liên ngày của từng nhóm confidence, kết hợp ngưỡng sàn cứng $c \ge 0.4$.
3. **Nguyên tắc Đồng nhất Tuyệt đối (Consistency Rule):**
   Cùng một danh sách cạnh và hệ thống trọng số $w_e$ này bắt buộc phải được áp dụng đồng bộ cho: (i) Hàm loss hiệu chuẩn SUMO, (ii) Cách tính baseline Historical Median, (iii) Sàn nhiễu $\Delta_{\text{noise}}$, và (iv) Tập kiểm định Test.
4. **Xử lý Mất tín hiệu Toàn cục (Global API Drop):**
   Nếu xảy ra sự cố server TomTom hoặc rớt mạng khiến toàn bộ mạng lưới đồng loạt có confidence thấp trong một chu kỳ:
   * **Áp dụng Mặt nạ hóa (Loss Masking):** SUMO vẫn tiếp tục chạy mô phỏng để duy trì tính liên tục của động lực học dòng xe, nhưng cửa sổ thời gian đó sẽ bị gắn mặt nạ (trọng số loss = 0), tuyệt đối **không tự tạo dữ liệu nội suy giả (no fake data interpolation)** đưa vào tập kiểm định.

---

## IV. BỘ BASELINE ĐỐI CHỨNG BẮT BUỘC & SÀN NHIỄU DỮ LIỆU (BENCHMARK ANCHORS)

### 4.1. Chứng minh Toán học về Sàn Nhiễu Lý thuyết (True Noise Floor)
Giả sử tốc độ thực tế tại cạnh $e$ theo các ngày có kỳ vọng $\mu_e(t)$ và chịu nhiễu ngẫu nhiên độc lập: $v_e^{(d)}(t) = \mu_e(t) + \epsilon_{e, d}(t)$ với $\mathbb{E}[\epsilon] = 0$ và $\text{Var}(\epsilon) = \sigma^2$.

* **Sai số đo lường giữa hai ngày làm việc độc lập $d_1$ và $d_2$:**
  $$\Delta v = v_{e}^{(d_2)} - v_{e}^{(d_1)} = \epsilon_{e, d_2} - \epsilon_{e, d_1}$$
  $$\text{Var}(\Delta v) = \text{Var}(\epsilon_{d_2}) + \text{Var}(\epsilon_{d_1}) = 2\sigma^2 \implies \Delta_{\text{noise}} = \sqrt{2}\sigma \implies \sigma = \frac{\Delta_{\text{noise}}}{\sqrt{2}}$$
* **Sai số của một mô hình mô phỏng hoàn hảo:**
  Mô hình hoàn hảo nhất dự báo đúng giá trị kỳ vọng thực $\hat{v} = \mu_e(t)$. Khi kiểm nghiệm trên ngày $d_2$:
  $$e_{\text{ideal}} = \mu_e(t) - v_e^{(d_2)}(t) = -\epsilon_{e, d_2}(t) \implies \text{RMSE}_{\text{ideal}} = \sqrt{\text{Var}(-\epsilon)} = \sigma = \frac{\Delta_{\text{noise}}}{\sqrt{2}}$$

```
Sai số Vận tốc (RMSE)
 ▲
 │   [THẤT BẠI]  Mô phỏng kém hơn giả định đường hoàn toàn vắng
 ┼────────────────────────────────────────────────────────── Free-flow Baseline (v0)
 │
 │   [KHÔNG CÓ GIÁ TRỊ THÊM]  Mô phỏng chỉ ngang bảng tra tĩnh
 ┼────────────────────────────────────────────────────────── Historical Median / Persistence (Delta_noise)
 │
 │   ★ [VÙNG ĐẠT CHUẨN KHOA HỌC] (Mô hình nắm bắt được động học mạng)
 │
 ┼ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Sàn Nhiễu Lý Thuyết (Delta_noise / sqrt(2))
 │   [VÙNG QUÁ KHỚP VÀO NHIỄU NGẪU NHIÊN CẢM BIẾN]
 └──────────────────────────────────────────────────────────► Cạnh / Thời gian
```

### 4.2. Bộ Ba Mốc Tham Chiếu
1. **Free-flow Baseline ($v_0$):** $\hat{v}_{e, \text{free}} = v_{0, e}$ (Giả định đường vắng).
2. **Historical Median Baseline:** Trung vị vận tốc của các ngày trong tập Train tại cùng khung giờ. Mô phỏng SUMO phải tiệm cận mức này trên ngày Test giữ lại để chứng minh có giá trị giải thích tương đương bảng tra có cùng thông tin.
3. **Sàn Nhiễu Lý Thuyết ($\sigma_{\text{floor}} = \Delta_{\text{noise}} / \sqrt{2}$):** Ngưỡng chặn dưới tối ưu. Mọi mô hình có RMSE nhỏ hơn ngưỡng này đều vi phạm nguyên lý Bayes và bị coi là quá khớp vào nhiễu ngẫu nhiên.

---

## V. BỘ CHỈ SỐ ĐÁNH GIÁ ĐỘNG HỌC VẬN TỐC ĐỘC LẬP (SPEED DYNAMICS METRICS)

1. **Sai số Vận tốc Tuyệt đối & Tương đối:**
   $$\text{RMSE}_v = \sqrt{\frac{1}{|\mathcal{E}|} \sum_{e \in \mathcal{E}} (\bar{v}_{\text{sim}, e} - v_{\text{obs}, e})^2}, \quad \text{MAE}_v = \frac{1}{|\mathcal{E}|} \sum_{e \in \mathcal{E}} |\bar{v}_{\text{sim}, e} - v_{\text{obs}, e}|$$
   $$\text{MRE}_v = \frac{1}{|\mathcal{E}|} \sum_{e \in \mathcal{E}} \frac{|\bar{v}_{\text{sim}, e} - v_{\text{obs}, e}|}{v_{0, e}} \times 100\%$$
2. **Tương quan Hạng Spearman Mức độ Nghẽn Mạng ($\rho_{\text{rank}}$):**
   Kiểm tra xem mô phỏng có nhận diện đúng thứ tự các tuyến đường tắc nhất trên bản đồ hay không:
   $$\rho_{\text{rank}} = 1 - \frac{6 \sum d_e^2}{|\mathcal{E}| (|\mathcal{E}|^2 - 1)}$$
3. **Độ Tương đồng Hình học Phân bố Vận tốc (Wasserstein Metric):**
   $$W_1(P_{\text{sim}}, P_{\text{obs}}) = \int_{0}^{\infty} |F_{\text{sim}}(v) - F_{\text{obs}}(v)| \, dv \quad [\text{km/h}]$$
   Báo cáo kèm khoảng cách cực đại Kolmogorov-Smirnov $D_{\text{KS}} = \sup_v |F_{\text{sim}} - F_{\text{obs}}|$ như một đại lượng mô tả hình học thuần túy (không dùng để ngụy biện bác bỏ).
4. **Ma trận Nhầm lẫn Phân loại Trạng thái Ùn tắc (LOS Matrix):**
   Phân 3 mức theo tỷ số $r = v / v_0$: Kẹt xe ($C: r < 0.40$), Ùn ứ ($S: 0.40 \le r \le 0.70$), Thông thoáng ($F: r > 0.70$). Tính toán Macro F1-Score và hệ số Cohen's Kappa $\kappa$.

---

## VI. PHƯƠNG PHÁP LUẬN THỐNG KÊ & CHỐNG GIẢ LẶP (STATISTICAL RIGOR)

### 6.1. Phân rã Thứ bậc Hai Tầng Ngẫu nhiên (Two-Stage Hierarchical Design)
Để loại trừ hiện tượng giả lặp (pseudo-replication) khi 4 simulation seeds nằm lồng trong 1 demand seed:

1. **Tổng hợp Vi mô Tầng 1 (Within-Demand Seed):**
   Với mỗi Demand Seed $j \in \{1, \dots, J\}$ ($J = 5$), chạy $K = 4$ Simulation Seeds và tính giá trị trung bình mạng lưới:
   $$\bar{Y}_j = \frac{1}{K} \sum_{k=1}^K Y_{j, k}$$
2. **Suy diễn Vĩ mô Tầng 2 (Between-Demand Seeds):**
   Thực hiện suy diễn trên đúng $J = 5$ quan sát độc lập $\{\bar{Y}_1, \dots, \bar{Y}_5\}$:
   $$\bar{Y} = \frac{1}{J} \sum_{j=1}^J \bar{Y}_j, \quad S_{\text{macro}} = \sqrt{\frac{1}{J - 1} \sum_{j=1}^J (\bar{Y}_j - \bar{Y})^2}$$
3. **Khoảng tin cậy 95% Student-$t$:**
   $$\mu_Y \in \left[ \bar{Y} - t_{0.975, \; J-1} \cdot \frac{S_{\text{macro}}}{\sqrt{J}}, \quad \bar{Y} + t_{0.975, \; J-1} \cdot \frac{S_{\text{macro}}}{\sqrt{J}} \right]$$
   *(Với $J = 5$, bậc tự do $df = 4$, hệ số tới hạn chính xác là $t_{0.975, 4} = 2{,}776$).*

### 6.2. Kiểm định Giả thuyết Ghép cặp Cấp độ Ngày (LODO Paired Test)
* Tổng hợp sai số về **cấp độ toàn mạng cho từng ngày kiểm định $d \in \{1, \dots, 5\}$** trong quy trình Leave-One-Day-Out:
  $$D_d = \text{RMSE}_{\text{SUMO}}^{(d)} - \text{RMSE}_{\text{Median}}^{(d)}$$
* Thực hiện Paired $t$-test trên mẫu $n = 5$ ngày độc lập ($df = 4$):
  $$t = \frac{\bar{D}}{S_D / \sqrt{5}}$$
* **Spatial Cluster Bootstrap theo Hành lang:** Lấy mẫu bootstrap lại theo từng cụm hành lang tuyến đường (trục Pasteur, Nam Kỳ Khởi Nghĩa, Hai Bà Trưng) thay vì lấy mẫu rời rạc từng cạnh, bảo toàn cấu trúc tự tương quan không gian.

---

## VII. ĐỊNH VỊ HỌC TĂNG CƯỜNG ĐA TÁC TỬ (MARL ROBUST POLICY HYPOTHESES)

Trong luận văn, sự bất định của ma trận nhu cầu được chuyển hóa thành một **Đóng góp Phương pháp luận thông qua Tối ưu hóa Chính sách Bền vững (Robust Policy Optimization / Domain Randomization)**:

> ### Các Giả thuyết Nghiên cứu Chính thức:
> * **Giả thuyết $H_1$ (Tính Bền vững):** *"Tác tử MARL được huấn luyện trong môi trường có xáo trộn nhu cầu (Domain Randomization $\mathcal{D} \sim \mathcal{U}(0{,}85 \cdot \boldsymbol{\lambda}^*, \; 1{,}15 \cdot \boldsymbol{\lambda}^*)$) sẽ duy trì mức trễ mạng thấp hơn có ý nghĩa thống kê so với tác tử chỉ được huấn luyện trên một kịch bản nhu cầu tĩnh $\boldsymbol{\lambda}^*$."*
> * **Giả thuyết $H_2$ (Khả năng Thích ứng Quá tải):** *"Khi đối mặt với sự biến động nhu cầu ngoài phân phối huấn luyện (Stress-test $\pm 30\%$), chính sách phối hợp mạng lưới của MARL (CoLight, MPLight) sẽ hạn chế được sự sụp đổ thông lượng (gridlock) tốt hơn các bộ điều khiển cố định (Fixed-time, Webster) và điều khiển cục bộ (Max-Pressure)."*
> * **Giả thuyết $H_{\text{oversat}}$ (Hiện trạng Quá bão hòa Đô thị):** *"Nhu cầu thực tế giờ cao điểm tại Quận 1 vượt trần dung lượng thiết kế TCVN ($V/C > 1.0$), là nguyên nhân cốt lõi gây sụt giảm vận tốc probe của TomTom về mức $v \le 10\text{ km/h}$."*

### Bộ Thuật toán Đối chuẩn Công bằng (Fair Benchmark Suite)
1. **Baseline Cổ điển:** Fixed-Time, Webster Method [Webster, 1958], Max-Pressure [Varaiya, 2013].
2. **Baseline MARL Kinh điển:** Independent DQN (IDQN), CoLight [Zheng et al., CIKM 2019], MPLight [Chen et al., AAAI 2020], PressLight [Wei et al., KDD 2019].

---

## VIII. MINH BẠCH HẠN CHẾ CỦA ĐỀ TÀI (METHODOLOGICAL LIMITATIONS)

1. **Thiếu Dữ liệu Lưu lượng Đếm thực (Absence of Ground-Truth Counts):** Nhu cầu là nhu cầu tổng hợp suy diễn từ tốc độ; không thể xác nhận độ chính xác tuyệt đối của lưu lượng từng nhánh rẽ.
2. **Bản chất Dữ liệu Probe Gom cụm của TomTom:** Dữ liệu phản ánh vận tốc trung bình không gian tổng hợp từ các phương tiện định vị, có độ trễ nhất định và tự động fallback về lịch sử khi mật độ thiết bị thấp.
3. **Giả định Thiết kế về Phương tiện Hỗn hợp:** Tỷ lệ xe máy ($80\%$) và tham số Sublane được thiết lập dựa trên tài liệu nghiên cứu trước (*Minh et al., 2005; Erdmann, 2015*), chưa được hiệu chuẩn riêng bằng camera thị giác máy tính tại từng nút giao.
4. **Hiện tượng Ràng buộc Nhập nhằng của Tham số $\lambda$:** Do chưa có kế hoạch pha đèn chi tiết ngoài hiện trường, tham số quy mô $\lambda$ có thể bù trừ cho sai số về năng lực nút và chu kỳ đèn.
5. **Giới hạn Khung Giờ & Điều kiện Thời tiết:** Dữ liệu thu thập ban ngày trong điều kiện bình thường; chưa tích hợp hiện tượng ngập nước triều cường hoặc sự cố tai nạn đột xuất.

---

## IX. LỘ TRÌNH THỰC NGHIỆM ĐỐI BỔ ĐA TẦNG: MẠNG ƯU TIÊN VÀ MẠNG TÍN HIỆU CỐ ĐỊNH (TWO-STAGE ABLATION & VALIDATION PROTOCOL)

Nhằm giải quyết triệt để sự nhập nhằng (confounding effect) giữa: (1) Nhu cầu dòng xe vĩ mô $\boldsymbol{\lambda}$, và (2) Sự can thiệp của chu kỳ pha đèn chưa tối ưu, nghiên cứu thiết lập quy trình thực nghiệm gồm 2 giai đoạn:

### 9.1. Giai đoạn 1: Mạng Ưu tiên Không Đèn Tín hiệu (Unsignalized Priority Network Testbed)
* **Mục đích:** Tách rời hoàn toàn ảnh hưởng của chu kỳ đèn cố định để cô lập và khảo sát năng lực thuần túy của bộ tạo nhu cầu tổng hợp $\lambda$.
* **Thiết lập:** Chuyển đổi toàn bộ 34 nút giao có đèn sang quyền ưu tiên hình học (`netconvert --traffic-light.remove true`).
* **Đặc tính dòng xe đo được:**
  - Tỷ lệ nạp mạng $ICR > 95\%$, tỷ lệ hoàn thành chuyến đi $TCR \approx 90\%$ (với $\lambda = 2.0\text{ xe/s}$, hoàn tất $6.081 / 6.762$ xe trong 1 giờ).
  - Vận tốc trung bình toàn mạng đạt $20{,}18\text{ km/h}$, phân bổ phương tiện đạt đúng $80{,}3\%$ xe máy, $14{,}6\%$ ô tô con, $5{,}1\%$ xe buýt.
* **Phân tích Cơ chế Sai số (Mechanistic Diagnostics):**
  - Mặc dù mạng lưới không bị sụp đổ thông lượng (gridlock), vận tốc trên các trục đại lộ chính (Lê Duẩn, Công Xã Paris, Nam Kỳ Khởi Nghĩa) lại cao hơn thực tế đáng kể ($v_{\text{sim}} \approx 36 - 38\text{ km/h}$ so với $v_{\text{obs}} \approx 8 - 15\text{ km/h}$).
  - *Nguyên nhân:* Không có đèn tín hiệu ngắt quãng, xe trên đường ưu tiên chạy với tốc độ tối đa liên tục, đồng thời luồng xe trên các nhánh rẽ phụ bị "đói quyền vào nút" (yield starvation), gây trễ cục bộ tại vài nhánh phụ trong khi hành lang chính hoàn toàn thông suốt.

### 9.2. Giai đoạn 2: Mạng Tín hiệu Chu kỳ Cố định (Fixed-Time Signalized Network Baseline)
* **Mục đích:** Đưa 34 bộ đèn tín hiệu với chu kỳ cố định (Fixed-time 90s, pha xanh/vàng 40s/5s/40s/5s) vào mạng lưới để tái hiện sự gián đoạn vận tốc định kỳ ngoài hiện trường.
* **Đánh giá So sánh:** Đánh giá xem sự hiện diện của điểm dừng đèn đỏ có kéo vận tốc hành lang về sát dải thực tế của TomTom ($15 - 20\text{ km/h}$) hay gây ùn ứ nếu tỷ lệ phân bổ thời gian xanh (green split) không thích ứng với lưu lượng.

---

## PHỤ LỤC A: THỐNG KÊ GEH & KIỂM TRA NHẤT QUÁN NỘI TẠI (SANITY CHECK)
Chỉ số GEH được giữ lại trong phần phụ lục như một công cụ kiểm tra độ ổn định toán học nội tại giữa lưu lượng mô phỏng $V_{\text{SUMO}}$ và lưu lượng ước tính sơ bộ qua BPR $V_{\text{BPR}}$, **không dùng làm căn cứ nghiệm thu tính chân thực với thực tế**:
$$GEH_e = \sqrt{\frac{2 \left( V_{\text{SUMO}, e} - V_{\text{BPR}, e} \right)^2}{V_{\text{SUMO}, e} + V_{\text{BPR}, e}}}$$

---

## PHỤ LỤC B: KIỂM SOÁT TỶ LỆ NẠP MẠNG (NETWORK INSERTION INTEGRITY)
Theo dõi các chỉ số từ thẻ `<step>` cuối cùng của tệp `--summary-output` như các tiêu chuẩn thực hành kỹ thuật mô phỏng để phòng ngừa tắc nghẽn biên làm sai lệch vận tốc bên trong:
* **Tỷ lệ Nạp mạng (ICR):** $N_{\text{inserted}} / N_{\text{loaded}} \ge 95{,}0\%$
* **Tỷ lệ Tồn đọng Cửa ngõ (GBR):** $N_{\text{waiting}} / N_{\text{loaded}} < 5{,}0\%$
* **Tỷ lệ Hoàn thành Chuyến đi (TCR):** $N_{\text{arrived}} / N_{\text{inserted}} \ge 80{,}0\%$

---

## TÀI LIỆU THAM KHẢO HỌC THUẬT (ACADEMIC REFERENCES)

1. **Oliehoek, F. A., & Amato, C.** (2016). *A Concise Introduction to Decentralized POMDPs*. Springer International Publishing. DOI: 10.1007/978-3-319-28929-8.
2. **Erdmann, J.** (2015). "SUMO's Lane-Changing Model." *Modeling Mobility with Open Data*, Lecture Notes in Mobility, Springer, Cham, pp. 99–123. DOI: 10.1007/978-3-319-25656-6_7.
3. **Lopez, P. A., et al.** (2018). "Microscopic Traffic Simulation using SUMO." *The 21st IEEE International Conference on Intelligent Transportation Systems (ITSC 2018)*, pp. 2575–2582. DOI: 10.1109/ITSC.2018.8569938.
4. **Minh, C. C., Sano, K., & Matsumoto, S.** (2005). "The speed, flow and headway analyses of motorcycle traffic." *Journal of the Eastern Asia Society for Transportation Studies*, 6, pp. 1496–1508.
5. **Dung, C. T., Miwa, T., Sato, H., & Morikawa, T.** (2015). "Analysis on Characteristics of Passenger Car and Motorcycle Fleets and Their Driving Conditions in Developing Country: A Case Study in Ho Chi Minh City, Vietnam." *Journal of the Eastern Asia Society for Transportation Studies*, 11, pp. 1096–1111.
6. **Varaiya, P.** (2013). "The max-pressure controller for arbitrary networks of signalized intersections." *Advances in Dynamic Network Modeling in Complex Systems*, pp. 27–66. Springer, New York, NY.
7. **Webster, F. V.** (1958). "Traffic Signal Settings." *Road Research Technical Paper No. 39*, Road Research Laboratory, HMSO, London.
8. **Zheng, G., et al.** (2019). "CoLight: Learning Network-level Cooperation for Traffic Signal Control." *Proceedings of the 28th ACM CIKM 2019*, pp. 1913–1922. DOI: 10.1145/3357384.3357900.
9. **Chen, C., Wei, H., et al.** (2020). "Toward A Thousand Lights: Decentralized Deep Reinforcement Learning for Large-Scale Traffic Signal Control." *Proceedings of the AAAI 2020*, 34(04), pp. 3414–3421. DOI: 10.1609/aaai.v34i04.5744.
10. **Wei, H., et al.** (2019). "PressLight: Learning Max-Pressure Control to Coordinate Traffic Signals in Arterial Networks." *Proceedings of the ACM KDD 2019*, pp. 1290–1298. DOI: 10.1145/3292500.3330949.
11. **Oregon Department of Transportation (ODOT)** (2011). *Protocol for Vissim Simulation*. Transportation Planning Analysis Unit (TPAU), Salem, OR.
12. **Bureau of Public Roads (BPR)** (1964). *Traffic Assignment Manual*. U.S. Department of Commerce, Washington, D.C.
13. **Transportation Research Board (TRB)** (2010). *Highway Capacity Manual (HCM 2010)*. National Research Council, Washington, D.C.
14. **Cascetta, E., Inaudi, D., & Marquis, G.** (1993). "Dynamic Estimators of Origin-Destination Matrices Using Traffic Counts, Quenching and Log-Linear Models." *Transportation Research Part B: Methodological*, 27(5), pp. 363–373.
15. **Hastie, T., Tibshirani, R., & Friedman, J.** (2009). *The Elements of Statistical Learning*. 2nd Edition, Springer, New York.
