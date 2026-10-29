# MATHEMATICS STRUCTURES MODELING TRAFFIC SIGNAL CONTRAL PROBLEM 

## I.Sơ lược về các cấu trúc toán  học trong mô hình hóa bài toán điều khiển  tín hiệu đèn giao thông bằng Agent RL
Các cấu trúc toán học sẽ được chia theo hai hướng: Single Agent, Multi Agent

**Single Agent:**

+ Standard MDP(1 nút giao thông)

+ Centralized MDP (gom toàn mạng lưới cho 1 agent xử lý).

**Multi Agent:**

+ Multi Agent MDP (Quan sát toàn cục)

+ Dec-MDP (Quan sát liên hợp đầy đủ)

+ Networked Dec-POMDP (Đồ thị mạng lưới)

+ Dec-POMDP 


<!--
Tổng hợp phần kiến thức của từng khung toán học
-->
**Đề xuất lựa chọn Dec-POMDP để làm khung toán học**

1. Phù hợp với Bản chất của Mạng lưới giao thông : Decentralized Excecution - tự đưa ra quyết định, giảm latecy. Phù hợp với tính quan sát 1 phần.
2. Giải pháp cho lời nguyền số chiều
3. Nền tảng của các thuật toán như PressLight, CoLight,..

**Hạn chế của Dec-POMDP**
1. Non-stationarity: môi trường thay đổi vì nhiều agent cùng học.
2. Scalability: số agent tăng làm không gian trạng thái và hành động bùng nổ.
3. Safe MARL: đảm bảo hành vi an toàn khi triển khai thực tế.


<!--
Quan tâm các papers này : 
https://arxiv.org/pdf/2602.20804

-->

Chi tiết kiến thức
Markov Decision Process: là một khung toán học mô hình hóa quá trình ra quyết định tuần tự, nơi kết quả phụ thuộc vào cả hành động của tác nhân (agent) và yếu tố ngẫu nhiên từ môi trường.
Bộ 5 thành phần cốt lõi của một Standard MDP $(S, A, P, R, \\gamma)$:
Tập trạng thái ($S - State\\ Space$): Mô tả tình trạng hiện tại của môi trường.
Tập hành động ($A - Action\\ Space$): Các lựa chọn hành động tác nhân có thể thực hiện.
Xác suất chuyển trạng thái ($P - Transition\\ Probability$): $P(s' | s, a) = \\mathbb{P}(S\_{t+1} = s' \\mid S_t = s, A_t = a)$, xác suất môi trường chuyển sang trạng thái $s'$ khi tác nhân thực hiện hành động $a$ tại trạng thái $s$.
Hàm phần thưởng ($R - Reward\\ Function$): $R(s, a, s')$, tín hiệu phản hồi lượng hóa chất lượng của hành động vừa thực hiện.
Hệ số chiết khấu ($\\gamma \\in \[0, 1\]$): Xác định tầm quan trọng của phần thưởng trong tương lai so với phần thưởng tức thì.
Tính chất Markov (Markov Property): Trạng thái tiếp theo $S\_{t+1}$ chỉ phụ thuộc vào trạng thái hiện tại $S_t$ và hành động hiện tại $A_t$, hoàn toàn độc lập với lịch sử các trạng thái trước đó. \[consider\] \[việc t+1 phụ thuộc vào t và t phụ thuộc vào t- 1 thì nó giống như 1 mạng RNN không ? Tức là nó có 1 mối quan hệ không phải là trực tiếp giữa các trạng thái ở xa đơn vị thời gian nhưng cũng là 1 mối quan hệ ngầm định giữa các trạng thái ở xa\]
Ta xem xét về hướng Centralized MDP (gom toàn bộ mạng lưới cho 1 agent):
S = S1, S2, S3,S4,…
A = A1, A2, A3,… =\> hệ quả: không gian trạng thái và hành động tăng theo cấp số nhân COD, khó hội tụ.
Hướng tiếp cận đa tác nhân (MARL)
Multi-Agent MDP (Quan sát toàn cục)
Khung toán học của Multi-Agent MDP Quan sát toàn cục cho hệ thống gồm $N$ tác nhân (với $N \> 1$) được cấu thành bởi bộ thành phần1:
$$\\left\\langle N, \\mathcal{S}, \\{\\mathcal{A}\_i\\}\_{i=1}^N, \\mathcal{P}, \\{\\mathcal{R}\_i\\}\_{i=1}^N, \\gamma \\right\\rangle$$
Tập trạng thái toàn cục ($\\mathcal{S}$): Mô tả đầy đủ tình trạng của toàn bộ môi trường hệ thống tại thời điểm $t$13.
Không gian hành động liên hợp (Joint Action Space - $\\mathcal{A}$\*\*)\*\*: Là tích Cartesian của các tập hành động riêng rẽ từ từng tác nhân: $$\\mathcal{A} = \\mathcal{A}\_1 \\times \\mathcal{A}\_2 \\times \\dots \\times \\mathcal{A}\_N$$ Trong đó, mỗi tác nhân $i$ chọn một hành động cá nhân $a_i \\in \\mathcal{A}\_i$12. Bộ hành động kết hợp được ký hiệu là $\\mathbf{a} = (a_1, a_2, \\dots, a_N)$45.
Hàm xác suất chuyển trạng thái (State Transition Dynamics - $\\mathcal{P}$\*\*)\*\*: $$\\mathcal{P}(s' \\mid s, a_1, a_2, \\dots, a_N) = \\mathbb{P}(S\_{t+1} = s' \\mid S_t = s, A\_{1,t} = a_1, \\dots, A\_{N,t} = a_N)$$ Trạng thái tiếp theo $s'$ của toàn bộ hệ thống phụ thuộc vào trạng thái hiện tại $s$ và sự kết hợp hành động đồng thời của tất cả $N$ tác nhân1.
Hàm phần thưởng của từng tác nhân (Reward Function - $\\mathcal{R}\_i$\*\*)\*\*: $$\\mathcal{R}\_i: \\mathcal{S} \\times \\mathcal{A}\_1 \\times \\dots \\times \\mathcal{A}\_N \\rightarrow \\mathbb{R}$$ Phần thưởng phản hồi $r_i$ trao cho tác nhân $i$ không chỉ phụ thuộc vào trạng thái $s$ và hành động $a_i$ của chính nó, mà còn chịu ảnh hưởng trực tiếp bởi hành động của tất cả các tác nhân khác trong mạng lưới16.
Đặc điểm Quan sát toàn cục (Global Observability): Mỗi tác nhân tại mọi bước thời gian đều có thể truy cập hoặc quan sát đầy đủ trạng thái hệ thống $s \\in \\mathcal{S}$ (hoặc thông tin từ tất cả các nút giao)1more_horiz.
Mục tiêu tối ưu hóa (Expected Discounted Return): Mỗi tác nhân $i$ tìm kiếm chiến lược $\\pi_i$ nhằm tối đa hóa tổng phần thưởng chiết khấu kỳ vọng tích lũy theo thời gian18: $$R_i = \\mathbb{E} \\left\[ \\sum\_{t=0}^{\\infty} \\gamma^t r\_{i,t} \\right\]$$ với $\\gamma \\in \[0, 1)$ là hệ số chiết khấu19.
ưu điểm và hạn chế của khung toán học này
Giải quyết vấn đề môi trường không dừng do các agent nhìn thấy được toàn bộ trạng thái của mạng giao thông.
Tăng khả năng phối hợp
hạn chế : Bùng nổ số chiều cho mỗi agent, truyền tải dữ liệu thời gian thực từ các điểm của mạng giao thông đến bộ xử lí, phương sai cao - do biến động rất lớn trong tín hiệu phần thưởng, làm quá trình huấn luyện bị chậm.
\*\* Biến thể:
Tập trung huấn luyện và thực thi phân tán.
Để khắc phục hạn chế về tính toán và truyền thông của Multi-Agent MDP thuần túy, các nghiên cứu tiên tiến (như thuật toán MADDPG) áp dụng cơ chế CTDE (Centralized Training, Decentralized Execution) dựa trên khung toán học này4more_horiz:
Giai đoạn Huấn luyện (Centralized Training): Mạng đánh giá (Critic) của từng tác nhân được phép truy cập trạng thái toàn cục $s$ và hành động liên hợp $(a_1, \\dots, a_N)$ để cập nhật hàm giá trị $Q_i(s, a_1, \\dots, a_N)$4more_horiz. Điều này triệt tiêu tình trạng không dừng trong quá trình học416.
Giai đoạn Thực thi (Decentralized Execution): Mạng quyết định (Actor) của mỗi nút giao $i$ chỉ cần nhận đầu vào là quan sát cục bộ $o_i$ tại chính nút giao đó để đưa ra hành động $a_i = \\mu_i(o_i)$, loại bỏ hoàn toàn sự phụ thuộc vào đường truyền mạng toàn cục khi triển khai thực tế4more_horiz.
Khung toán học DEC MDP (Decentralized Markov Decision Process - Quan sát liên hợp đầy đủ)
Một Dec-MDP hợp tác dành cho hệ thống $N$ tác nhân ($N \> 1$) được định nghĩa bởi bộ 7 thành phần toán học:
$$\\left\\langle N, \\mathcal{S}, \\{\\mathcal{A}\_i\\}\_{i=1}^N, \\mathcal{P}, \\{\\Omega_i\\}\_{i=1}^N, \\mathcal{O}, \\mathcal{R}, \\gamma \\right\\rangle$$
Tập tác nhân ($N$): Số lượng bộ điều khiển đèn tín hiệu giao thông trong mạng lưới.
Tập trạng thái toàn cục ($\\mathcal{S}$): Không gian trạng thái thực tế/ẩn của toàn bộ môi trường giao thông.
Không gian hành động liên hợp ($\\mathcal{A} = \\mathcal{A}\_1 \\times \\mathcal{A}\_2 \\times \\dots \\times \\mathcal{A}\_N$): Mỗi tác nhân $i$ chọn hành động cá nhân $a_i \\in \\mathcal{A}\_i$ (như chọn/chuyển pha đèn)1. Bộ hành động kết hợp đồng thời của toàn hệ thống là $\\mathbf{a} = (a_1, a_2, \\dots, a_N) \\in \\mathcal{A}$.
Hàm xác suất chuyển trạng thái ($\\mathcal{P}$): $$\\mathcal{P}(s' \\mid s, \\mathbf{a}) = \\mathbb{P}(S\_{t+1} = s' \\mid S_t = s, A_t = \\mathbf{a})$$ Xác suất mạng lưới chuyển từ trạng thái toàn cục $s$ sang $s'$ phụ thuộc vào trạng thái hiện tại $s$ và bộ hành động liên hợp $\\mathbf{a}$.
Tập quan sát cục bộ ($\\Omega_i$) và Hàm quan sát ($\\mathcal{O}$): Mỗi tác nhân $i$ chỉ nhận được một quan sát cục bộ $o_i \\in \\Omega_i$. Hàm quan sát $\\mathcal{O}(\\mathbf{o} \\mid s, \\mathbf{a})$ xác định xác suất tạo ra bộ quan sát liên hợp $\\mathbf{o} = (o_1, o_2, \\dots, o_N)$ từ trạng thái $s$ và hành động $\\mathbf{a}$.
Hàm phần thưởng ($\\mathcal{R}$): Tín hiệu phần thưởng phản hồi (như giảm thời gian chờ hay độ dài hàng đợi xe)1. Trong Dec-MDP hợp tác, phần thưởng thường là phần thưởng chung $\\mathcal{R}(s, \\mathbf{a})$ hoặc phần thưởng riêng $\\mathcal{R}\_i(s, \\mathbf{a})$ cho từng nút giao1.
Hệ số chiết khấu ($\\gamma \\in \[0, 1)$): Tỷ lệ chiết khấu giá trị phần thưởng trong tương lai.
Tính chất Quan sát liên hợp đầy đủ
Khái niệm hơi khó hiểu
ý nghĩa toán học:
Trong Dec-POMDP, dù gộp tất cả quan sát $o_1, \\dots, o_N$ lại, thông tin vẫn bị thiếu sót hoặc nhiễu (mang tính chất POMDP).
Trong Dec-MDP, thông tin không bị mất mà chỉ bị phân tán (decentralized). Môi trường chỉ mang tính chất "bị ẩn" với từng tác nhân đơn lẻ, nhưng hoàn toàn "hiện rõ" đối với tập hợp tất cả tác nhân.
Mô hình toán học của Dec-POMDP cho hệ thống $N$ nút giao ($N \> 1$) được định nghĩa bởi bộ thành phần $\\langle \\mathcal{S}, \\mathcal{A}\_1 \\dots \\mathcal{A}\_N, \\mathbb{P}, \\mathcal{R}\_1 \\dots \\mathcal{R}\_N, \\Omega_1 \\dots \\Omega_N, \\mathcal{O}, \\gamma \\rangle$46:
Trạng thái hệ thống ($\\mathcal{S}$): Biểu diễn trạng thái thực tế/ẩn của toàn bộ mạng lưới giao thông (như lưu lượng và phân bố xe thực tế trên toàn tuyến)5.
Hành động liên hợp ($\\mathcal{A} = \\mathcal{A}\_1 \\times \\dots \\times \\mathcal{A}\_N$): Tích Cartesian của các tập hành động cá nhân7. Mỗi tác nhân $i$ chọn hành động $a_i \\in \\mathcal{A}\_i$ là một pha đèn không xung đột từ tập pha khả thi $\\Phi$78.
Không gian quan sát cục bộ ($\\Omega_i$) và Hàm quan sát ($\\mathcal{O}$): Do không thể truy cập trạng thái toàn cục $\\mathcal{S}$, mỗi nút giao $i$ chỉ nhận được một quan sát cục bộ $o_i \\in \\Omega_i$ thông qua xác suất quan sát $\\mathcal{O}(o_i \\mid s, a)$ từ các cảm biến tại chỗ (như thời gian chờ, số lượng xe hoặc độ dài hàng đợi trên các làn đường vào)5more_horiz.
Hàm xác suất chuyển trạng thái ($\\mathbb{P}$ hay $\\mathcal{T}$): Xác định xác suất chuyển trạng thái tiếp theo $\\mathbb{P}(s' \\mid s, a_1, \\dots, a_N)$, phụ thuộc đồng thời vào trạng thái hiện tại và hành động liên hợp của tất cả các nút giao46.
Hàm phần thưởng ($\\mathcal{R}\_i$): Tín hiệu phản hồi lượng hóa chất lượng điều khiển (như giảm tổng thời gian chờ hoặc độ dài hàng đợi xe) tại từng nút giao6more_horiz.
Thách thức cốt lõi: môi trường không dừng: Hành động chuyển đèn pha của 1 nút giao thông sẽ thay đổi trực tiếp luồng xe đi chuyển sang các nút lân cận. Khi các  nút cùng nhau học và thay đổi chiến lược thì quan sát cục bộ của từng nút bị biến đđộng liên tục.  Vi phạm tính chất markov =\> các thuật toán đơn lẻ như Q learning khó hội tụ , mất ổn định.
Cơ chế thực thi: Centralized training with decentralized execution
Huấn luyện tập trung : Mạng đánh giá critic của thuật toán  truy cập vào trạng thái bổ sung / bộ hành động liên hợp của tất cả các nút giao Q_i =\> Mục đích: triệt tiêu tính không dừng trong quá trình tính toán cập nhật giá trị hàm giá trị.
Thực thi phân tán: Actor của mỗi nút giao quan sát cục bộ o_i đưa ra quyết định của đèn qua a_i

Hãy chỉnh sửa lại file kiến thức tổng quát này để trông dễ nhìn, và review lại các lý thuyết ở đây. tôi tổng hợp chúng từ notebooklm 