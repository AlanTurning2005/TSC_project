# CƠ SỞ LÝ THUYẾT VỀ ĐỘ NHẠY HÀM BPR, PHÂN TÍCH PHẢN BIỆN BÀI TOÁN NGHỊCH ĐẢO CỤC BỘ VÀ NỀN TẢNG CHUYỂN DỊCH SANG HIỆU CHUẨN ĐỘNG HỌC $\boldsymbol{\lambda}(t)$
## (Theoretical Foundation of BPR Sensitivity, Analytical Disproof of Local Inversion, and Paradigm Shift to Dynamic Network Demand Calibration)

---

> [!IMPORTANT]
> ### ĐỊNH VỊ HỌC THUẬT & CẢNH BÁO PHÂN ĐỊNH PHẠM VI (ACADEMIC SCOPE & DEPRECATION NOTICE)
> * **Bản chất của tài liệu này:** Đây là **Bản Khảo sát Nền tảng Lý thuyết & Phân tích Phản biện Giải tích (Theoretical Foundation & Analytical Disproof Whitepaper)** của đề tài nghiên cứu MARL-TSC tại TP. Hồ Chí Minh.
> * **Tuyên bố Khai tử (Deprecation Notice):** Hướng tiếp cận *nghịch đảo hàm BPR độc lập trên từng đoạn đường kết hợp tối ưu hóa tham số cục bộ bằng thuật toán Bayesian (Optuna)* là **bước nghiên cứu khám phá ban đầu ĐÃ BỊ LOẠI BỎ HOÀN TOÀN (DEPRECATED & DISCONTINUED)** do các giới hạn cấu trúc toán học (điểm kỳ dị, bài toán nghịch đảo ill-posed, vi phạm định luật bảo toàn dòng Kirchhoff). Toàn bộ mã nguồn thử nghiệm cũ (`calibrate_bpr_optuna.py`) đã được xóa bỏ khỏi codebase dự án.
> * **Hướng tiếp cận Chính thức của Đề tài:** Phương pháp luận chính thức duy nhất được công nhận và triển khai là mô hình **Hiệu chuẩn Nhu cầu Động học Toàn mạng $\boldsymbol{\lambda}(t)$ (Dynamic Demand Scaling with Network Flow Conservation & Sublane Model)**, được quy chuẩn chi tiết tại tệp [SD_EVALUATION.md](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/docs/SD_EVALUATION.md) và mã nguồn [calibrate_demand_slices.py](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/02_calibration/calibrate_demand_slices.py). Trong hệ hình mới này, hàm BPR chỉ giữ vai trò là một **Rào chắn Dung sai Mềm (Soft Sanity Boundary)** phục vụ kiểm tra tính hợp lý vật lý và kiểm chứng Giả thuyết Khoa học $H_{\text{oversat}}$.
> * **Mục đích tài liệu:** Cung cấp kho dữ liệu chứng minh giải tích toán học và cơ sở vật lý giao thông vững chắc phục vụ việc trích xuất nội dung cho **Bài báo Khoa học Quốc tế (Paper)**, **Khóa luận Tốt nghiệp (Thesis)**, và **Báo cáo Chuyên đề / Phản biện Miệng (Seminar & Oral Defense)**.

---

## MỤC LỤC
1. [Khung Toán học BPR Thuận & Động cơ Kỹ thuật Ban đầu](#1-khung-toán-học-bpr-thuận--động-cơ-kỹ-thuật-ban-đầu)
2. [Chứng minh Giải tích Đạo hàm, Độ co giãn & Điểm kỳ dị](#2-chứng-minh-giải-tích-đạo-hàm-độ-co-giãn--điểm-kỳ-dị)
   * 2.1. Phân tích Dung lượng đường $C$ (Capacity): Tuyến tính quy mô ($\mathcal{E}_C = 1.0$)
   * 2.2. Phân tích Hệ số trễ cận biên $\alpha$ (Alpha): Kém co giãn ($|\mathcal{E}_\alpha| < 1.0$)
   * 2.3. Phân tích Số mũ độ dốc quá tải $\beta$ (Beta): Phi tuyến mũ & Đổi chiều phản ứng
   * 2.4. Phân tích Biến quan trắc Vận tốc $v$ (Speed) & Điểm kỳ dị tiệm cận tự do ($\lim_{v \to v_0} \mathcal{E}_v = -\infty$)
3. [Đặc tính Vật lý Dòng xe máy Hỗn hợp TP. Hồ Chí Minh](#3-đặc-tính-vật-lý-dòng-xe-máy-hỗn-hợp-tp-hồ-chí-minh)
4. [Mổ xẻ Phản biện: Tại sao Nghịch đảo BPR & Tối ưu Cục bộ là Ngõ cụt Phương pháp luận?](#4-mổ-xẻ-phản-biện-tại-sao-nghịch-đảo-bpr--tối-ưu-cục-bộ-là-ngõ-cụt-phương-pháp-luận)
   * 4.1. Bài toán nghịch đảo thiếu ràng buộc nghiêm trọng (Ill-posed Inverse Problem & Equifinality)
   * 4.2. Vùng phẳng bão hòa sâu & Hiện tượng trôi dạt tham số ($\partial v / \partial V \approx 0$)
   * 4.3. Vi phạm Định luật Bảo toàn Dòng Giao thông (Kirchhoff's Flow Conservation)
   * 4.4. Phản biện việc chắp vá gò ép dải tham số từ nghiên cứu ngoại lai
   * 4.5. Bằng chứng sụp đổ thực nghiệm: Sự cố bùng nổ 798k xe
5. [Tuyên bố Khai tử Chính thức & Phân định Phạm vi Mã nguồn](#5-tuyên-bố-khai-tử-chính-thức--phân-định-phạm-vi-mã-nguồn)
6. [Bước Chuyển dịch Hệ hình sang Hiệu chuẩn Động học Toàn mạng $\boldsymbol{\lambda}(t)$](#6-bước-chuyển-dịch-hệ-hình-sang-hiệu-chuẩn-động-học-toàn-mạng-boldsymbollambdat)
   * 6.1. Sinh luồng toàn mạng có bảo toàn dòng qua `randomTrips` + `duarouter`
   * 6.2. Tái định vị vai trò của BPR: Rào chắn Dung sai Mềm (Soft Boundary)
   * 6.3. Kiểm chứng Giả thuyết Khoa học về Hiện tượng Quá bão hòa ($H_{\text{oversat}}$)
7. [Hướng dẫn Trích xuất Nội dung cho Paper, Khóa luận & Seminar](#7-hướng-dẫn-trích-xuất-nội-dung-cho-paper-khóa-luận--seminar)
   * 7.1. Trích đoạn chuẩn mực cho Bài báo Khoa học (Paper - 1 Paragraph)
   * 7.2. Khung cấu trúc cho Chương Phương pháp luận Khóa luận Tốt nghiệp (Thesis - 2 Pages)
   * 7.3. Kịch bản Phản biện Miệng trước Hội đồng (Oral Defense - 45 Seconds)
8. [Tài liệu Tham khảo Chuẩn Quốc tế & Mã BibTeX](#8-tài-liệu-tham-khảo-chuẩn-quốc-tế--mã-bibtex)

---

## 1. KHUNG TOÁN HỌC BPR THUẬN & ĐỘNG CƠ KỸ THUẬT BAN ĐẦU

### 1.1. Bối cảnh Kỹ thuật Thực tế tại TP. Hồ Chí Minh
Trong các đô thị đang phát triển như TP. Hồ Chí Minh (khu vực lõi Quận 1 và Quận 3), việc xây dựng mô hình mô phỏng giao thông vi mô đối mặt với rào cản dữ liệu nghiêm trọng:
* **Không có hệ thống cảm biến vòng từ (Induction Loop Detectors) hay camera đếm xe tự động phủ kín 66 vị trí quan trắc huyết mạch.**
* Nguồn dữ liệu số thời gian thực duy nhất và liên tục có được là **vận tốc hành trình (Probe Vehicle Speed)** thu thập từ TomTom Traffic Flow API (Endpoint `flowSegmentData`: vận tốc tức thời $v_{\text{curr}}$, vận tốc tự do $v_{\text{free}}$, độ tin cậy $\text{confidence}$).

### 1.2. Trực giác Kỹ thuật Cổ điển (The Intuitive Formulation)
Để chuyển đổi dữ liệu vận tốc quan trắc được thành nhu cầu lưu lượng phương tiện $V$ (Volume) phục vụ mô phỏng vi mô SUMO, trực giác kỹ thuật ban đầu của các kỹ sư giao thông là áp dụng hàm trở kháng của Cục Đường bộ Mỹ (Bureau of Public Roads - BPR, 1964) [1] theo chiều nghịch đảo.

#### Phương trình BPR thuận:
Liên hệ giữa vận tốc lưu thông trung bình $v$ và lưu lượng dòng xe $V$ trên một đoạn đường:

$$v = \frac{v_0}{1 + \alpha \left( \frac{V}{C} \right)^\beta}$$

*Trong đó:*
* $v$: Vận tốc hành trình trung bình trên đoạn đường $[\text{km/h}]$.
* $v_0$: Vận tốc trong điều kiện dòng tự do (Free-flow speed) $[\text{km/h}]$.
* $C$: Dung lượng thiết kế thông hành thực tế của đoạn đường $[\text{PCU/h}]$ hoặc $[\text{xe/h}]$.
* $\alpha$: Hệ số trễ cận biên (định thời điểm bắt đầu suy giảm vận tốc).
* $\beta$: Số mũ xác định độ dốc sụt giảm vận tốc khi dòng xe tiến vào trạng thái quá tải.

#### Dẫn xuất Phương trình BPR nghịch đảo:
Với giả định $v \le v_0$, thực hiện biến đổi đại số:

$$\frac{v_0}{v} = 1 + \alpha \left( \frac{V}{C} \right)^\beta \iff \alpha \left( \frac{V}{C} \right)^\beta = \frac{v_0 - v}{v}$$

Lũy thừa bậc $1/\beta$ hai vế:

$$V(C, \alpha, \beta; v, v_0) = C \cdot \left[ \frac{1}{\alpha} \left( \frac{v_0 - v}{v} \right) \right]^{1/\beta} = C \cdot \alpha^{-1/\beta} \cdot X^{1/\beta}$$

Với $X = \frac{v_0 - v}{v} \ge 0$ là tỷ lệ suy giảm vận tốc tương đối do ùn tắc.

---

## 2. CHỨNG MINH GIẢI TÍCH ĐẠO HÀM, ĐỘ CO GIÃN & ĐIỂM KỲ DỊ

Để đánh giá độ nhạy và mức độ rủi ro sai số của từng thành phần trong phương trình nghịch đảo, ta xét **Độ co giãn cục bộ (Point Elasticity $\mathcal{E}$)**. Đại lượng $\mathcal{E}_p$ đo lường tỷ lệ phần trăm biến thiên của lưu lượng $V$ khi tham số $p$ thay đổi $1\%$:

$$\mathcal{E}_p = \frac{\partial \ln V}{\partial \ln p} = \frac{\partial V}{\partial p} \cdot \frac{p}{V}$$

Lấy logarit tự nhiên hai vế của hàm BPR nghịch đảo:
$$\ln V = \ln C - \frac{1}{\beta} \ln \alpha + \frac{1}{\beta} \ln \left( \frac{v_0 - v}{v} \right)$$

---

### 2.1. Phân tích Dung lượng đường $C$ (Capacity)
Lấy đạo hàm riêng của $\ln V$ theo $\ln C$:

$$\mathcal{E}_C = \frac{\partial \ln V}{\partial \ln C} = \mathbf{1.0}$$

#### Nhận xét Toán học:
* Độ co giãn $\mathcal{E}_C = 1.0$ là hằng số bất biến ở mọi dải vận tốc.
* $C$ đóng vai trò là **Hệ số tỷ lệ quy mô tuyến tính bậc 1 (Linear Scale Multiplier)**: Dung lượng $C$ lệch $+10\%$ sẽ kéo theo lưu lượng ước tính $V$ lệch đúng $+10\%$.

---

### 2.2. Phân tích Hệ số trễ cận biên $\alpha$ (Alpha)
Lấy đạo hàm riêng của $\ln V$ theo $\ln \alpha$:

$$\mathcal{E}_\alpha = \frac{\partial \ln V}{\partial \ln \alpha} = \mathbf{-\frac{1}{\beta}}$$

#### Nhận xét Toán học:
* Vì đối với mọi dòng giao thông thực tế, số mũ $\beta > 1.0$ (thường $\beta \in [1.8, 4.0]$), ta luôn có:
  $$|\mathcal{E}_\alpha| = \frac{1}{\beta} < 1.0$$
* **Tính chất kém co giãn (Inelasticity):** Biến thiên của $\alpha$ bị nén lại theo lũy thừa nghịch đảo $1/\beta$. Ví dụ với $\beta = 2.5$, $|\mathcal{E}_\alpha| = 0.40$ (khi $\alpha$ tăng $10\%$, $V$ chỉ giảm $4\%$). $\alpha$ là tham số có độ nhạy thấp nhất.

---

### 2.3. Phân tích Số mũ độ dốc quá tải $\beta$ (Beta)
Lấy đạo hàm riêng của $V = C \cdot \exp \left( \frac{1}{\beta} \ln \left( \frac{X}{\alpha} \right) \right)$ theo $\beta$:

$$\frac{\partial V}{\partial \beta} = V \cdot \left[ -\frac{1}{\beta^2} \ln \left( \frac{X}{\alpha} \right) \right] = -\frac{V}{\beta} \ln \left( \frac{V}{C} \right)$$

Độ co giãn theo $\beta$:

$$\mathcal{E}_\beta = \frac{\partial V}{\partial \beta} \cdot \frac{\beta}{V} = \mathbf{-\frac{1}{\beta} \ln \left( \frac{V}{C} \right)}$$

#### Nhận xét Toán học:
* **Tính chất đổi chiều phi tuyến (Nonlinear Sign Inversion):**
  * Vùng dưới bão hòa ($V < C \iff V/C < 1$): $\ln(V/C) < 0 \implies \mathcal{E}_\beta > 0$ ($\beta$ tăng làm $V$ tăng).
  * Vùng đúng điểm bão hòa ($V = C \iff V/C = 1$): $\ln(V/C) = 0 \implies \mathcal{E}_\beta = 0$ ($\beta$ hoàn toàn mất tác dụng).
  * Vùng quá bão hòa cao điểm ($V > C \iff V/C > 1$): $\ln(V/C) > 0 \implies \mathcal{E}_\beta < 0$ ($\beta$ tăng làm $V$ sụt giảm rất sâu).
* $\beta$ là tham số phi tuyến cực kỳ nhạy cảm và nguy hiểm, thay đổi bản chất tác động tùy theo trạng thái giao thông.

---

### 2.4. Phân tích Biến quan trắc Vận tốc $v$ & Điểm kỳ dị tiệm cận tự do
Khảo sát đạo hàm của $V$ đối với chính biến số đầu vào từ cảm biến vệ tinh $v$:

$$\frac{\partial V}{\partial v} = C \alpha^{-1/\beta} \cdot \frac{1}{\beta} \left( \frac{v_0 - v}{v} \right)^{\frac{1}{\beta} - 1} \cdot \left( -\frac{v_0}{v^2} \right) = -\frac{V}{\beta} \left( \frac{v_0}{v(v_0 - v)} \right) < 0$$

Độ co giãn theo vận tốc $v$:

$$\mathcal{E}_v = \frac{\partial V}{\partial v} \cdot \frac{v}{V} = \mathbf{-\frac{1}{\beta} \left( \frac{v_0}{v_0 - v} \right)}$$

```
Độ co giãn theo Vận tốc (|E_v|)
 ▲
 │                                 /│ (Tiến tới Vô cực: Singularity)
 │                                / │
 │                               /  │
 │                              /   │
 │                             /    │
 │                            /     │
 │                           /      │
 ┼──────────────────────────/───────┼─────────────────────────► Vận tốc v
 0                         v*      v0 (Free-flow Speed)
 (Tắc đường)                       (Đường thông thoáng)
```

#### Phân tích Điểm kỳ dị (Singularity Proof):
* Khi dòng giao thông thông thoáng (đêm khuya, sáng sớm hoặc giữa trưa), vận tốc thực tế tiệm cận vận tốc tự do:
  $$v \to v_0 \implies (v_0 - v) \to 0 \implies \lim_{v \to v_0} \mathcal{E}_v = -\infty$$
* **Hệ quả thực tế khốc liệt:**  
  Tại vùng $v \approx v_0$, mẫu số triệt tiêu khiến độ nhạy tiến tới vô cực. Bất kỳ một dao động nhiễu ngẫu nhiên nào của GPS TomTom (ví dụ vận tốc đổi từ $29.5 \to 28.5\text{ km/h}$, chỉ lệch $1\text{ km/h}$) cũng khiến lưu lượng $V$ tính toán **nhảy vọt từ vài chục xe lên hàng nghìn xe**. Đây chính là **nguồn nhiễu sơ cấp làm bùng nổ số lượng phương tiện**.

---

## 3. ĐẶC TÍNH VẬT LÝ DÒNG XE MÁY HỖN HỢP TP. HỒ CHÍ MINH

Từ phân tích toán học trên, ta giải thích được tại sao việc áp đặt các bộ tham số ngoại lai vào mạng lưới trung tâm TP.HCM đều dẫn đến sai lệch nghiêm trọng:

### 3.1. Sự Thất bại của Tham số Chuẩn Mỹ (FHWA / BPR 1964: $\alpha = 0.15, \beta = 4.0$)
* **Đặc tính phương Tây:** Dòng xe thuần túy ô tô tuân thủ làn cứng. Khi nhu cầu vượt dung lượng ($V/C > 1$), xe buộc phải dừng nối đuôi nhau, tốc độ rơi thẳng đứng như một bức tường $\implies$ phù hợp với số mũ dốc đứng $\beta = 4.0$.
* **Đặc tính TP.HCM:** Xe máy chiếm tỷ trọng áp đảo ($>85\%$) với đặc tính **thẩm thấu qua khe hở (Motorcycle Porosity / Seepage)** [Minh et al., 2005]. Khi đường quá bão hòa ($V/C = 1.2 - 1.5$), ô tô bị cầm chân nhưng xe máy vẫn luồn lách qua các khoảng trống bên hông để duy trì tốc độ bò chậm ($8 - 12\text{ km/h}$). Đường cong vận tốc không bao giờ sập thẳng đứng.
* **Hệ quả:** Nếu ép $\beta = 4.0$ vào hàm BPR nghịch đảo tại TP.HCM, số mũ $1/4 = 0.25$ sẽ dìm lưu lượng giờ cao điểm xuống mức thấp phi lý, không phản ánh được hiện tượng tích tụ mật độ cực lớn.

### 3.2. Sự Không Tương thích của Tham số Tham chiếu Quốc tế (Singh 1999, Kumar & Rao 2013)
* Các nghiên cứu tại Ấn Độ của Singh (1999) [2] ($\beta = 2.29$) và Kumar & Rao (2013) [3] ($\beta = 2.04$) đã ghi nhận độ dốc thoai thoải của dòng hỗn hợp.
* Tuy nhiên, việc sao chép nguyên trạng các tham số này sang trung tâm Quận 1 & Quận 3 vẫn thất bại do:
  1. **Tỷ lệ xe máy tại TP.HCM ($>85\%$) cao hơn đáng kể** so với dòng hỗn hợp tại Ấn Độ (nơi tỷ lệ xe ba bánh tự hành auto-rickshaw và ô tô con cao hơn).
  2. **Tác động ma sát bên cực đoan (Severe Side Friction):** Mật độ điểm giao cắt dày đặc ($50 - 150\text{m}$), hoạt động kinh doanh buôn bán ven đường và việc dừng đỗ xe tràn lan kéo giảm vận tốc dòng xe từ rất sớm, ngay cả khi $V/C$ còn thấp ($0.4 - 0.5$).

---

## 4. MỔ XẺ PHẢN BIỆN: TẠI SAO NGHỊCH ĐẢO BPR & TỐI ƯU CỤC BỘ LÀ NGÕ CỤT PHƯƠNG PHÁP LUẬN?

Nhóm nghiên cứu đã từng thử nghiệm việc sử dụng thuật toán tối ưu hóa siêu tham số Bayesian (Optuna / Tree-structured Parzen Estimator - TPE) để "học" tự động bộ tham số $(\alpha, \beta)$ tối ưu cho từng đoạn đường từ dữ liệu tốc độ TomTom. Tuy nhiên, hướng đi này đã **sụp đổ hoàn toàn cả về mặt lý luận giải tích lẫn thực nghiệm mô phỏng**.

Dưới đây là 5 lập luận phản biện học thuật chứng minh phương pháp này sai từ bản chất:

```
                      SỰ SỤP ĐỔ CỦA MÔ HÌNH NGHỊCH ĐẢO BPR CỤC BỘ
                      
  [Vận tốc TomTom v_obs] ──► [Nghịch đảo BPR từng cạnh] ──► [Lưu lượng rời rạc V_e]
           ▲                                                        │
           │ (Cố ép số bằng Optuna)                                  ▼ (Nạp vào SUMO)
   [Quá khớp nhiễu cảm biến] ◄── [Sụp đổ lưới: 798k xe] ◄── [Vi phạm bảo toàn dòng]
```

### 4.1. Bài toán Nghịch đảo Thiếu Ràng buộc Nghiêm trọng (Ill-posed Inverse Problem & Equifinality)
* Tại mỗi thời điểm trên mỗi đoạn đường $e$, ta chỉ có **một giá trị quan trắc duy nhất** là vận tốc vô hướng $v_e(t)$.
* Từ một phương trình đại số với một đại lượng đo đạc, việc cố gắng ước lượng đồng thời 4 ẩn số $(\alpha_e, \beta_e, C_e, V_e)$ là một bài toán **nghịch đảo không chỉnh (ill-posed inverse problem)**.
* Theo nguyên lý *Equifinality* (nhiều nguyên nhân cùng dẫn đến một kết quả): Có vô số bộ tổ hợp $(\alpha, \beta, C, V)$ khác nhau cùng tạo ra đúng một giá trị vận tốc $v$. Thuật toán Bayesian Optimization khi tối ưu hóa độc lập từng cạnh chỉ đơn thuần tìm một bộ số ngẫu nhiên làm cực tiểu hóa hàm lỗi số học trên tập huấn luyện, hoàn toàn mất đi ý nghĩa vật lý thực tế.

### 4.2. Vùng Phẳng Bão hòa Sâu & Hiện tượng Trôi dạt Tham số ($\partial v / \partial V \approx 0$)
Khi mạng lưới bước vào giờ cao điểm tắc nghẽn sâu ($V > C$), vận tốc thực tế sụt giảm về sàn bò ($v \approx 5 - 10\text{ km/h}$) và giữ nguyên ở đó dù lưu lượng có tiếp tục tăng:
$$\frac{\partial v}{\partial V} \approx 0 \quad (\text{khi } V > C)$$
Tại vùng này, bề mặt hàm mất mát (loss landscape) bị phẳng lì. Thuật toán tối ưu hóa hoàn toàn mất gradient thông tin định hướng, dẫn đến hiện tượng **trôi dạt tham số (parameter drift)**: Các giá trị $\alpha, \beta$ có thể nhảy vọt đến các cực trị phi lý mà không làm thay đổi sai số vận tốc.

### 4.3. Vi phạm Định luật Bảo toàn Dòng Giao thông (Kirchhoff's Flow Conservation)
* Bản chất của hàm BPR là **Hàm Trở kháng Liên kết tĩnh (Static Link Performance Function)** phục vụ bài toán phân bổ lưu lượng vĩ mô (Traffic Assignment). Nó hoàn toàn không chứa đựng cơ chế bảo toàn dòng trên cấu trúc không gian mạng lưới.
* Khi dùng thuật toán tối ưu độc lập từng cạnh $e \in \mathcal{E}$, 66 vị trí quan trắc bị xé rời thành 66 bài toán cô lập. Kết quả là tại các nút giao tín hiệu $u$, định luật bảo toàn dòng Kirchhoff bị phá vỡ hoàn toàn:
  $$\sum_{e \in \mathcal{E}_{\text{in}}(u)} V_e(t) \neq \sum_{e' \in \mathcal{E}_{\text{out}}(u)} V_{e'}(t)$$
* Khi nạp các giá trị lưu lượng rời rạc này vào bộ giả lập vi mô SUMO, các phương tiện xuất hiện cục bộ từ hư không tại đầu mỗi cạnh và biến mất ở cuối cạnh, tạo ra các xung đột giao cắt giả tạo (artificial blocking) khiến mạng lưới bị tê liệt nhân tạo.

### 4.4. Phản biện Việc Chắp vá Gò ép Dải Tham số Ngoại lai
* Nhận thấy thuật toán tối ưu hóa tự do cho ra kết quả phân kỳ, một giải pháp "chữa cháy" thường thấy là cố gắng thu hẹp không gian tìm kiếm $[\alpha_{\text{min}}, \alpha_{\text{max}}]$ và $[\beta_{\text{min}}, \beta_{\text{max}}]$ dựa vào các giá trị công bố trong các bài báo nước ngoài (như Singh 1999 hay Kumar & Rao 2013).
* Tuy nhiên, đây là **ngụy biện phương pháp luận vòng vo (circular reasoning / ad-hoc patching)**: Khi mô hình toán nghịch đảo đã sai ở cấp độ cấu trúc (thiếu bảo toàn dòng và có điểm kỳ dị), việc gò ép biên tham số từ các đô thị nước ngoài không giải quyết được gốc rễ bài toán, mà chỉ tạo ra một sự khớp nối gượng ép che giấu sự bất ổn định nội tại.

### 4.5. Bằng chứng Sụp đổ Thực nghiệm: Sự cố Bùng nổ 798k Xe
* Trong giai đoạn thử nghiệm sơ khởi của đề tài, mô hình nghịch đảo BPR kết hợp Optuna đã ước tính nhu cầu giao thông trên mạng lưới Quận 1 lên tới **798.492 phương tiện trong vòng 6 giờ**.
* Con số này vượt gấp hơn **10 lần tổng dung lượng hình học tối đa** của toàn bộ mặt cắt đường hiện hữu. Khi đưa vào mô phỏng SUMO vi mô, mạng lưới sụp đổ hoàn toàn (gridlock toàn phần) chỉ sau chưa đầy 15 phút mô phỏng, phương tiện không thể nạp vào mạng (tỷ lệ chèn mạng $ICR < 15\%$). Đây là bằng chứng thực nghiệm dứt khoát xác nhận sự thất bại của hướng tiếp cận này.

---

## 5. TUYÊN BỐ KHAI TỬ CHÍNH THỨC & PHÂN ĐỊNH PHẠM VI MÃ NGUỒN

> [!CAUTION]
> ### BIÊN BẢN KHAI TỬ PHƯƠNG PHÁP LUẬN (FORMAL DEPRECATION RECORD)
> 1. **Bãi bỏ Toàn diện:** Nhóm nghiên cứu **chính thức tuyên bố loại bỏ hoàn toàn (DEPRECATED)** hướng tiếp cận sử dụng hàm BPR nghịch đảo và các thuật toán tối ưu hóa tham số cục bộ ($\alpha, \beta, C$) để ước lượng lưu lượng nạp mạng vi mô.
> 2. **Dọn dẹp Không gian Mã nguồn:** Toàn bộ các mô-đun mã nguồn thử nghiệm liên quan (bao gồm `calibrate_bpr_optuna.py`, `calibrate_bpr_optuna.ipynb` và `evaluate_simulation_geh.py`) đã được gỡ bỏ khỏi nhánh phát triển chính thức của dự án (được ghi nhận trong lịch sử commit Git `d7ea6ec`).
> 3. **Cảnh báo cho Cộng sự và Hội đồng:** Tuyệt đối không tiếp tục nghiên cứu, phục hồi hay đề xuất các giải pháp "tinh chỉnh tham số BPR" nhằm mục đích sinh dòng xe nạp mạng. Mọi phân tích BPR trong đề tài kể từ thời điểm này trở đi chỉ được hiểu theo đúng định vị tại Mục 6 dưới đây.

---

## 6. BƯỚC CHUYỂN DỊCH HỆ HÌNH SANG HIỆU CHUẨN ĐỘNG HỌC TOÀN MẠNG $\boldsymbol{\lambda}(t)$

Nhận thức rõ khuyết tật của việc nghịch đảo cục bộ, nghiên cứu đã thực hiện **chuyển dịch hệ hình phương pháp luận (Methodological Paradigm Shift)** sang bài toán: **Hiệu chuẩn Quy mô Nhu cầu Động học Toàn mạng $\boldsymbol{\lambda}(t)$ có Bảo toàn Dòng Không gian**.

```
                           HỆ HÌNH PHƯƠNG PHÁP LUẬN CHUẨN TẮC MỚI
                           
       [Đồ thị Mạng lưới G = (V, E)] + [Dữ liệu Vận tốc TomTom v_obs(t)]
                                     │
                                     ▼
        [Sinh Luồng Tuyến đường Toàn mạng có Bảo toàn Dòng (Network OD Trips)]
         (randomTrips.py + duarouter / fringe-factor=8.0 / min-distance=400m)
                                     │
                                     ▼
         [Ước lượng Đồng thời Vector Quy mô Nhu cầu Toàn mạng λ(t) ∈ R^K]
            (Simultaneous Regularized Optimization qua Bộ giả lập vi mô SUMO)
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
            [Hàm Mất mát Vận tốc]             [Rào chắn Dung sai Mềm BPR]
              min RMSE_v(λ)                      P_BPR^norm(λ) <= Boundary
```

### 6.1. Sinh Luồng Toàn Mạng Bảo toàn Dòng qua `randomTrips` + `duarouter`
Thay vì tự tạo dòng xe cục bộ tại từng mép đường, mạng lưới được cấp phát dòng xe thông qua giải thuật định tuyến Dijkstra thích ứng, đảm bảo tính bảo toàn dòng và phản ánh đúng quy luật di chuyển đô thị:
* **Hệ số Nạp Vành đai (`--fringe-factor 8.0`):** Buộc dòng xe phải bắt nguồn từ các cửa ngõ vành đai đổ vào trung tâm theo các trục đại lộ huyết mạch, phản ánh đúng tính chất luồng xuyên tâm (through-trips).
* **Khoảng cách Chuyến đi Tối thiểu (`--min-distance 400.0` m):** Triệt tiêu hiện tượng xe vừa xuất hiện đã rẽ ngay gây tắc nghẽn nhân tạo.
* **Mô hình Dòng Hỗn hợp Chia làn phụ (Heterogeneous Sublane Model):** Tích hợp `--lateral-resolution 0.25` và tỷ lệ thực tế $85\%$ xe máy, $12\%$ ô tô con, $3\%$ xe buýt (chuẩn hóa theo `HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md`).

### 6.2. Tái định vị Vai trò của BPR: Rào chắn Dung sai Mềm (Soft Boundary)
Trong hệ hình mới, **hàm BPR hoàn toàn không tham gia vào việc sinh lưu lượng xe**. Vai trò duy nhất của BPR được chuyển hóa thành một **Rào chắn Dung sai Mềm Phi thứ nguyên (Dimensionless Soft BPR Regularizer)** bên trong hàm mục tiêu tối ưu hóa vector $\boldsymbol{\lambda}(t)$ (quy định tại Mục 2.3 của [SD_EVALUATION.md](file:///c:/Users/DANH/Desktop/DS_full/.vscode/TSC_project/macro_traffic_crawler/docs/SD_EVALUATION.md)):

$$\min_{\boldsymbol{\lambda}} \mathcal{L}(\boldsymbol{\lambda}) = \text{RMSE}_v(\boldsymbol{\lambda}) + \gamma_{\text{smooth}} \sum_{k=2}^{K-1} (\lambda_{k+1} - 2\lambda_k + \lambda_{k-1})^2 + \gamma_{\text{prior}} \|\boldsymbol{\lambda} - \boldsymbol{\lambda}_{\text{prior}}\|^2 + w_{\text{pen}} \cdot \mathcal{P}_{\text{BPR}}^{\text{norm}}(\boldsymbol{\lambda})$$

Trong đó, hàm phạt vi phạm dung lượng vật lý được định nghĩa:
$$\mathcal{P}_{\text{BPR}}^{\text{norm}}(\boldsymbol{\lambda}) = \frac{1}{|\mathcal{E}|} \sum_{e \in \mathcal{E}} \left[ \left( \frac{\max(0, \; \underline{V}_e - V_{\text{sim}, e}(\boldsymbol{\lambda}))}{C_e} \right)^2 + \left( \frac{\max(0, \; V_{\text{sim}, e}(\boldsymbol{\lambda}) - \bar{V}_e)}{C_e} \right)^2 \right]$$

#### Cơ chế Xử lý $w_{\text{pen}}$ 2 bước theo Sàn nhiễu:
1. **Bước 1 (A Priori Check):** Chạy tối ưu hóa với $w_{\text{pen}} = 0$. Nếu lưu lượng mô phỏng $V_{\text{sim}, e}$ tự nhiên nằm trong khoảng dung lượng hợp lý, BPR trở thành chỉ số hậu kiểm (Sanity Check), triệt tiêu hoàn toàn $w_{\text{pen}}$.
2. **Bước 2 (Định lượng theo Sàn nhiễu):** Nếu xảy ra vi phạm vượt trần vật lý, $w_{\text{pen}}$ được định lượng theo công thức neo vào sàn nhiễu tự nhiên $\Delta_{\text{noise}}$:
   $$w_{\text{pen}} = \frac{\Delta_{\text{noise}}}{(\delta^*)^2} \approx \frac{2.5}{0.04} \approx 62.5\text{ km/h}$$

### 6.3. Kiểm chứng Giả thuyết Khoa học về Hiện tượng Quá bão hòa ($H_{\text{oversat}}$)
Rào chắn BPR cho phép cận trên $\bar{V}_e$ nới rộng đến $1.3 C_e$ để phục vụ kiểm chứng **Giả thuyết Khoa học $H_{\text{oversat}}$**:
> *"Tại các trục hành lang huyết mạch khu vực Quận 1 và Quận 3 trong giờ cao điểm sáng, nhu cầu giao thông thực tế đã vượt trần dung lượng thiết kế TCVN ($V/C > 1.0$), là nguyên nhân cốt lõi gây sụt giảm vận tốc probe về mức sàn $v \le 10\text{ km/h}$."*

---

## 7. HƯỚNG DẪN TRÍCH XUẤT NỘI DUNG CHO PAPER, KHÓA LUẬN & SEMINAR

Tài liệu này được cấu trúc để có thể trích xuất trực tiếp thành các văn bản học thuật ở các cấp độ khác nhau:

### 7.1. Trích đoạn Chuẩn mực cho Bài báo Khoa học (Paper - 1 Paragraph)
*Vị trí đề xuất: Mục Traffic Demand Formulation hoặc Related Work (khoảng 10-12 dòng):*
> *"Unlike conventional approaches that attempt to invert the classical BPR link performance function directly from probe velocities, this study identifies that such local inversion leads to an ill-posed inverse problem with infinite speed elasticity ($\lim_{v \to v_0} \mathcal{E}_v = -\infty$) near free-flow conditions and severely violates Kirchhoff's flow conservation across network nodes. Consequently, rather than estimating link-level flows, we introduce a holistic dynamic demand scaling framework $\boldsymbol{\lambda}(t)$ governed by second-order smoothness regularization and network-wide shortest path routing. In this formulation, BPR is strictly retained as a dimensionless soft sanity boundary to penalize physically implausible edge-level capacities while evaluating urban oversaturation phenomena."*

### 7.2. Khung Cấu trúc cho Chương Phương pháp luận Khóa luận Tốt nghiệp (Thesis - 2 Pages)
* **Tiểu mục 3.2.1: Giới hạn Lý thuyết của Hàm BPR Nghịch đảo trong Dòng Hỗn hợp Đô thị:**
  * Trình bày công thức BPR thuận và phép biến đổi nghịch đảo.
  * Đưa ra các công thức đạo hàm độ co giãn ($\mathcal{E}_C, \mathcal{E}_\alpha, \mathcal{E}_\beta, \mathcal{E}_v$).
  * Nhấn mạnh chứng minh điểm kỳ dị tiệm cận tự do và tính kém xác định (Equifinality).
* **Tiểu mục 3.2.2: Phân tích Thất bại Thực nghiệm và Bước Chuyển dịch sang $\boldsymbol{\lambda}(t)$:**
  * Trình bày nguyên nhân sụp đổ lưu lượng khi tối ưu cục bộ từng đoạn đường.
  * Giới thiệu mô hình tối ưu hóa đồng thời vector quy mô nhu cầu toàn mạng $\boldsymbol{\lambda}(t)$ tích hợp mô hình Sublane.
  * Trình bày công thức số hạng phạt dung sai mềm BPR phi thứ nguyên và cơ chế kiểm soát $w_{\text{pen}}$.

### 7.3. Kịch bản Phản biện Miệng trước Hội đồng (Oral Defense - 45 Seconds)
*Khi Hội đồng chất vấn về việc tại sao không dùng BPR tính lưu lượng từng cạnh:*
> *"Kính thưa Hội đồng, nhóm đã nghiên cứu rất sâu hướng tiếp cận này. Tuy nhiên, về mặt toán học giải tích, việc nghịch đảo BPR từ vận tốc là một bài toán nghịch đảo thiếu ràng buộc (ill-posed), có điểm kỳ dị với độ co giãn bùng nổ vô hạn khi tốc độ tiệm cận tự do ($\lim_{v \to v_0} \mathcal{E}_v = -\infty$). Quan trọng hơn, việc tối ưu BPR độc lập từng cạnh vi phạm định luật bảo toàn dòng Kirchhoff tại các nút giao, từng khiến mô phỏng vi mô bị kích ảo lên gần 800 nghìn xe và sụp đổ hoàn toàn. Do đó, nhóm đã chứng minh hướng đi này là ngõ cụt lý thuyết và quyết định chuyển dịch sang phương pháp Hiệu chuẩn Quy mô Nhu cầu Toàn mạng $\boldsymbol{\lambda}(t)$ có bảo toàn dòng, đồng thời chuyển BPR về đúng vai trò của nó là rào chắn kiểm tra biên vật lý mềm."*

---

## 8. TÀI LIỆU THAM KHẢO CHUẨN QUỐC TẾ & MÃ BIBTEX

### 8.1. Danh mục Tài liệu Trích dẫn
1. **Bureau of Public Roads (BPR)** (1964). *Traffic Assignment Manual*. U.S. Department of Commerce, Urban Planning Division, Washington, D.C.
2. **Singh, R.** (1999). "Improved speed-flow relationships for congested travel on freeways and arterials in developing cities." *Transportation Research Record*, 1678(1), pp. 170–176. DOI: 10.3141/1678-21.
3. **Kumar, P. K. H., & Rao, K. V. R.** (2013). "Calibration of speed flow relationship for mixed traffic conditions." *Journal of the Indian Roads Congress*, 74(3), pp. 273–284.
4. **Minh, C. C., Sano, K., & Matsumoto, S.** (2005). "The speed, flow and headway analyses of motorcycle traffic." *Journal of the Eastern Asia Society for Transportation Studies*, 6, pp. 1496–1508.
5. **Transportation Research Board (TRB)** (2010). *Highway Capacity Manual (HCM 2010)*. National Research Council, Washington, D.C.
6. **Cascetta, E., Inaudi, D., & Marquis, G.** (1993). "Dynamic Estimators of Origin-Destination Matrices Using Traffic Counts, Quenching and Log-Linear Models." *Transportation Research Part B: Methodological*, 27(5), pp. 363–373. DOI: 10.1016/0191-2615(93)90012-M.
7. **Hastie, T., Tibshirani, R., & Friedman, J.** (2009). *The Elements of Statistical Learning: Data Mining, Inference, and Prediction*. 2nd Edition, Springer Series in Statistics, Springer, New York.
8. **Bộ Khoa học và Công nghệ** (2007). *Tiêu chuẩn Quốc gia TCVN 104:2007: Đường đô thị - Yêu cầu thiết kế*. NXB Xây dựng, Hà Nội.

---

### 8.2. Khối BibTeX phục vụ Overleaf / LaTeX Khóa luận

```bibtex
@techreport{bpr1964traffic,
  author      = {{Bureau of Public Roads}},
  title       = {Traffic Assignment Manual},
  institution = {U.S. Department of Commerce, Urban Planning Division},
  year        = {1964},
  address     = {Washington, D.C.}
}

@article{singh1999improved,
  author    = {Singh, Ravindra},
  title     = {Improved speed-flow relationships for congested travel on freeways and arterials in developing cities},
  journal   = {Transportation Research Record},
  volume    = {1678},
  number    = {1},
  pages     = {170--176},
  year      = {1999},
  doi       = {10.3141/1678-21}
}

@article{kumar2013calibration,
  author    = {Kumar, P. K. H. and Rao, K. V. R.},
  title     = {Calibration of speed flow relationship for mixed traffic conditions},
  journal   = {Journal of the Indian Roads Congress},
  volume    = {74},
  number    = {3},
  pages     = {273--284},
  year      = {2013}
}

@article{minh2005speed,
  author    = {Minh, C. C. and Sano, K. and Matsumoto, S.},
  title     = {The speed, flow and headway analyses of motorcycle traffic},
  journal   = {Journal of the Eastern Asia Society for Transportation Studies},
  volume    = {6},
  pages     = {1496--1508},
  year      = {2005}
}

@book{hcm2010,
  author    = {{Transportation Research Board}},
  title     = {Highway Capacity Manual (HCM 2010)},
  publisher = {National Research Council},
  year      = {2010},
  address   = {Washington, D.C.}
}

@article{cascetta1993dynamic,
  author    = {Cascetta, Ennio and Inaudi, Domenico and Marquis, G.},
  title     = {Dynamic Estimators of Origin-Destination Matrices Using Traffic Counts, Quenching and Log-Linear Models},
  journal   = {Transportation Research Part B: Methodological},
  volume    = {27},
  number    = {5},
  pages     = {363--373},
  year      = {1993},
  doi       = {10.1016/0191-2615(93)90012-M}
}

@book{hastie2009elements,
  author    = {Hastie, Trevor and Tibshirani, Robert and Friedman, Jerome},
  title     = {The Elements of Statistical Learning: Data Mining, Inference, and Prediction},
  edition   = {2nd},
  publisher = {Springer},
  year      = {2009},
  address   = {New York}
}

@standard{tcvn104_2007,
  title        = {TCVN 104:2007 - Urban roads: Design requirements},
  organization = {Ministry of Science and Technology of Vietnam},
  year         = {2007},
  address      = {Hanoi, Vietnam}
}
```
