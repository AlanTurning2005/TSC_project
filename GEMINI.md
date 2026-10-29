# Bộ Quy chuẩn Nghiên cứu Học thuật: MARL in Traffic Signal Control

## 1. Liêm chính Học thuật & Nguồn trích dẫn (Academic Integrity)
- **Zero Hallucination đối với số liệu thực nghiệm**: Tuyệt đối không tự bịa kết quả so sánh (ví dụ: tự cho ATT giảm 25% khi chưa có dữ liệu/chưa chạy mô phỏng).
- **Trích dẫn chuẩn học thuật**: Mọi định lý, công thức, số liệu từ tài liệu phải dẫn nguồn chuẩn IEEE/ACM/TRB: `[Tác giả, Năm, Tên hội nghị/tạp chí, Section/Table cụ thể]`.
- **Hỗ trợ định dạng BibTeX**: Khi trích dẫn một bài báo, luôn sẵn sàng xuất trích dẫn dạng BibTeX để đưa vào LaTeX/Overleaf của khóa luận.
- **Kiểm chứng trên nhiều nguồn**: Papers phải được tìm thấy ở ít nhất 2,3 trang uy tín như Scholar, Arvix, Scihub, ReSearchGate...  để đảm bảo papers có tồn tại và được công nhận. 
-**Tính minh bạch**: Khi đọc 1 papers và gặp phải 1 trích dẫn, muốn tái sử dụng trích dẫn đó cũng cần các bước kiểm chứng học thuật về trích dẫn đó.
## 2. Chuẩn hóa Khung Toán học (Mathematical Formulation)
- Mọi mô hình MARL phải được định nghĩa tường minh theo khung **Dec-POMDP** với bộ 7 thành phần:
  $\langle \mathcal{N}, \mathcal{S}, \{\mathcal{A}_i\}, \mathcal{P}, \{\mathcal{R}_i\}, \{\mathcal{O}_i\}, \gamma \rangle$
- **Ký hiệu nhất quán**:
  - Không gian trạng thái $o_i \in \mathcal{O}_i$: độ dài hàng đợi (queue), thời gian chờ (delay), số lượng xe (vehicle counts), áp lực (pressure).
  - Không gian hành động $a_i \in \mathcal{A}_i$: chuyển pha (phase switch) hoặc điều chỉnh thời lượng xanh (green split).
  - Hàm thưởng $r_i$: viết rõ công thức toán học và đơn vị, giải thích lý do thiết kế (tránh Sparse Reward).

## 3. Tính Công bằng trong Thực nghiệm & So sánh Baseline
- Khi so sánh với baseline, bắt buộc phải đối chiếu trên **cùng điều kiện**:
  - Baseline truyền thống: Fixed-time, Webster (tính theo công thức lưu lượng bão hòa), Max-Pressure.
  - Baseline RL/MARL kinh điển: Independent DQN (IDQN), CoLight (GNN/Attention), PressLight/MPLight.
- Luôn yêu cầu chạy trên **ít nhất 3 - 5 random seeds** để lấy trung bình và độ lệch chuẩn (mean ± std), không chỉ lấy seed tốt nhất.
- Khi một tham số chưa được bài báo công bố hoặc chưa chạy thực tế: Bắt buộc gắn nhãn `[GIẢ ĐỊNH / CHƯA CHẠY THỰC NGHIỆM]` và nêu lý do chọn giá trị đó.

## 4. Xử lí số liệu học thuật
- Đảm bảo được số liệu đó nằm trong nghiên cứu nào, phải có nguồn, trích dẫn thực tế. Tránh tình trạng bịa đặt thông tin hay mơ hồ về câu trả lời. 

## 5. Tông giọng & Phong cách Khoa học
- Giữ phong cách khách quan, phân tích đa chiều (nêu rõ cả ưu điểm và hạn chế, ví dụ: MARL phối hợp tốt nhưng chi phí giao tiếp communication overhead cao, hoặc môi trường không dừng non-stationary).

