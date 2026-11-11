# Bộ Quy chuẩn Nghiên cứu Học thuật: MARL in Traffic Signal Control

## 0. Hệ Mục tiêu Nghiên cứu Cốt lõi (Core Research Objectives)

### Mục tiêu 1 (Core Objective): Thiết kế, Huấn luyện MARL Agents cho TSC & Đánh giá Đối chuẩn
- **Mục tiêu chính:** Thiết kế và huấn luyện các tác tử học tăng cường đa tác tử (MARL - Multi-Agent Reinforcement Learning) để điều khiển đèn tín hiệu giao thông (có thể tiếp cận theo khung toán học Dec-POMDP; kiến trúc tác tử có thể là độc lập hoặc có cơ chế giao tiếp, tương tác qua lại).
- **Thiết kế mở (Open Design):** Không ràng buộc cứng nhắc thuật toán cụ thể (CoLight, IDQN chỉ là các phương án tham khảo, không phải mục tiêu bắt buộc). Thiết kế không gian trạng thái (Input), không gian hành động (Output) và hàm phần thưởng sẽ được nghiên cứu, tinh chỉnh linh hoạt trong quá trình thực nghiệm.
- **Đối chuẩn so sánh (Benchmarking):** Đem agent sau khi huấn luyện đối chiếu, so sánh với các baseline:
  - *Bộ điều khiển truyền thống:* Fixed-Time (chu kỳ cố định), Actuated / Actual-Time (thời gian thực thích ứng), hoặc các quy tắc heuristics khác.
  - *Mô hình học máy / MARL:* So sánh với các agents từ các bài báo khoa học đã công bố trong lĩnh vực TSC.
- **Đánh giá khách quan:** Đo lường hiệu năng dựa trên các chỉ số giao thông tiêu chuẩn (thời gian hành trình, độ trễ mạng lưới, chiều dài hàng đợi, lưu lượng thông thoát...) trên cùng điều kiện kịch bản và các hạt giống ngẫu nhiên (seeds).

### Mục tiêu 2 (Core Objective): Xây dựng Bộ Dữ liệu & Môi trường Thử nghiệm TP.HCM (Vietnam - HCMC Benchmark Testbed)
- **Mạng lưới thực địa:** Môi trường mô phỏng vi mô SUMO tại khu vực trung tâm TP.HCM (khu vực Quận 1 & Quận 3 với các nút giao có đèn tín hiệu thực tế).
- **Đặc thù giao thông Việt Nam:** Phản ánh chân thực dòng giao thông hỗn hợp không phân làn với tỷ lệ xe máy áp đảo, tận dụng mô hình vi mô SUMO Sublane để tái hiện hành vi lách làn và tương tác vật lý giữa các dòng phương tiện.
- **Hiệu chuẩn bằng dữ liệu thực tế (Khái quát):** Nhu cầu dòng xe được nạp và hiệu chuẩn dựa trên dữ liệu giao thông thực tế (dữ liệu TomTom Traffic Flow hoặc dữ liệu quan trắc thực địa). Phương pháp hiệu chỉnh được giữ linh hoạt và có thể tinh chỉnh theo các bước thực nghiệm.
- **Khả năng đối chuẩn chéo:** Duy trì pipeline có thể kết nối hoặc đối chuẩn với các bộ dữ liệu phổ biến (như CityFlow) để kiểm tra tính tổng quát hóa của giải pháp.

### Mục tiêu 3 [OPTIONAL / TÙY CHỌN]: Khảo sát Tính Bất định Tổng hợp (Synthetic Uncertainty & Robustness)
> **Quy tắc ưu tiên thời gian:** Đây là mục tiêu **TÙY CHỌN (OPTIONAL)**. Toàn bộ nguồn lực tập trung hoàn thành Mục tiêu 1 và Mục tiêu 2. Chỉ quay lại triển khai Mục tiêu 3 khi còn dư thời gian nghiên cứu.
- **Mục đích:** Khảo sát khả năng thích ứng và phản ứng của các agents đã huấn luyện khi đối mặt với các kịch bản bất định tổng hợp (biến động lưu lượng đột biến, nhiễu tín hiệu quan sát, hoặc sự cố nghẽn mạng).

---

## 1. Liêm chính Học thuật & Nguồn trích dẫn (Academic Integrity)
- **Zero Hallucination đối với số liệu thực nghiệm**: Tuyệt đối không tự bịa kết quả so sánh (ví dụ: tự cho ATT giảm 25% khi chưa có dữ liệu/chưa chạy mô phỏng).
- **Trích dẫn chuẩn học thuật**: Mọi định lý, công thức, số liệu từ tài liệu phải dẫn nguồn chuẩn IEEE/ACM/TRB: `[Tác giả, Năm, Tên hội nghị/tạp chí, Section/Table cụ thể]`.
- **Hỗ trợ định dạng BibTeX**: Khi trích dẫn một bài báo, luôn sẵn sàng xuất trích dẫn dạng BibTeX để đưa vào LaTeX/Overleaf của khóa luận.

## 2. Chuẩn hóa Khung Toán học (Mathematical Formulation)
- Khi mô hình hóa toán học cho bài toán MARL, khuyến khích sử dụng khung **Dec-POMDP** với bộ 7 thành phần tổng quát:
  $\langle \mathcal{N}, \mathcal{S}, \{\mathcal{A}_i\}, \mathcal{P}, \{\mathcal{R}_i\}, \{\mathcal{O}_i\}, \gamma \rangle$
- **Tính linh hoạt trong thiết kế:** Không gian quan sát $o_i \in \mathcal{O}_i$, không gian hành động $a_i \in \mathcal{A}_i$ và hàm thưởng $r_i$ sẽ do tác giả chủ động lựa chọn và thử nghiệm để tối ưu cho bài toán cụ thể.

## 3. Tính Công bằng trong Thực nghiệm & So sánh Baseline
- Khi so sánh với baseline, bắt buộc phải đối chiếu trên **cùng điều kiện**:
  - Chạy trên **nhiều random seeds** (ít nhất 3 - 5 seeds) để lấy giá trị trung bình và độ biến động, tránh cherry-picking seed tốt nhất.
  - Khi một tham số chưa được bài báo công bố hoặc chưa chạy thực tế: Bắt buộc gắn nhãn `[GIẢ ĐỊNH / CHƯA CHẠY THỰC NGHIỆM]` và nêu lý do chọn giá trị đó.

## 4. Tông giọng & Phong cách Khoa học
- Giữ phong cách khách quan, phân tích đa chiều (nêu rõ cả ưu điểm và hạn chế của từng phương pháp tiếp cận).

---

## 5. Liêm chính Mô phỏng & Chống Ngụy biện Dữ liệu (Simulation Integrity & Anti-Gaming)
- **5.1. Cấm Dùng Dữ liệu Lịch sử làm Thế thân (Zero Surrogate Leakage):**
  - Tuyệt đối nghiêm cấm mọi hành vi lấy ma trận Historical Median hoặc dữ liệu quan trắc thực tế (Ground Truth) cộng/trừ độ lệch để ngụy tạo làm ma trận vận tốc mô phỏng $v_{\text{sim}}$.
  - Ma trận $v_{\text{sim}}$ dùng cho đánh giá khoa học BẮT BUỘC phải được trích xuất trực tiếp từ đầu ra vi mô thật của phần mềm mô phỏng (tệp `edgedata.xml`, `tripinfo.xml` của SUMO).
- **5.2. Cấm Gán Cứng Chỉ số Mạng lưới (Zero Hardcoded Telemetry):**
  - Các chỉ số động học mạng: Tỷ lệ Hoàn thành Chuyến (TCR), Tỷ lệ Teleport, Độ trễ dừng chờ ($\bar{T}_{\text{loss}}$) bắt buộc phải được tính toán từ các tệp cảm biến `summary.xml` và `tripinfo.xml` của lượt mô phỏng tương ứng.
  - Tuyệt đối nghiêm cấm việc gán tĩnh (hardcode) các giá trị đẹp (ví dụ: $TCR = 94.12\%$, $\text{teleport} = 0.0\%$) trong mã nguồn đánh giá.
- **5.3. Phân định Rạch ròi giữa Chế độ Kiểm thử (Dry-run) và Nghiệm thu Chính thức:**
  - Chế độ Dry-Run (chỉ dùng để test cú pháp đường ống, kiểm tra shape ma trận) phải được kích hoạt tường minh bằng cờ `--dry-run`.
  - Kết quả từ chế độ Dry-Run BẮT BUỘC phải gắn nhãn `[DRY_RUN / SYNTHETIC]` và TUYỆT ĐỐI KHÔNG ĐƯỢC ghi đè vào các tệp kết quả nghiệm thu chính thức (`level1_lodo_results.json`).
  - Mọi tệp báo cáo benchmark chính thức phải có trường metadata chứng thực: `is_real_sumo_simulation: true`, thời gian chạy thực tế, và tổng số phương tiện được mô phỏng.
- **5.4. Kiểm soát Chi phí & Bùng nổ Tính toán trong Mô hình Vi mô Sublane:**
  - Đối với dòng xe máy hỗn hợp TP.HCM, cấu hình tham số Sublane phải bảo đảm tính khả thi về mặt thời gian: khuyến nghị `step-length = 0.4s` và `lateral-resolution = 0.40m` cho các bài toán tối ưu hóa vĩ mô/trung mô.
  - Bắt buộc tích hợp cơ chế Watchdog Timeout (tối đa 10 - 15 phút/trial) và tự ngắt nếu phát hiện gridlock để tránh lãng phí tài nguyên CPU.
- **5.5. Tôn trọng Giới hạn Vật lý của Hệ số Điều khiển Cơ sở (Baseline Physics):**
  - Chu kỳ đèn cố định Fixed-Time 90s khi chịu tải cao điểm xe máy TP.HCM chắc chắn sẽ xuất hiện ùn ứ cục bộ và phân tán sai số vận tốc ($\text{Var}(e) \approx 12 - 14\text{ km/h}$). Đây là hiện tượng vật lý tự nhiên, là bằng chứng khoa học cho thấy sự cần thiết của MARL, tuyệt đối không được "làm đẹp số liệu" bằng cách ghìm non tải.

