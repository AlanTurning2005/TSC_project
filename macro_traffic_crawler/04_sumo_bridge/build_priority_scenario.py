"""
build_priority_scenario.py
Tự động chuyển đổi mạng lưới SUMO (.net.xml) có đèn tín hiệu (TLS)
thành mạng lưới hoàn toàn ưu tiên (Priority Unsignalized Network)
và tạo một kịch bản mô phỏng độc lập tại sumo_scenarios/q1_priority_unsignalized/.

Lý do học thuật & kỹ thuật:
- Khi chưa có dữ liệu đo đạc thực địa về chu kỳ đèn và thời lượng pha xanh tại các nút giao,
  việc áp đặt chu kỳ mặc định của SUMO (fixed-time không kiểm chuẩn) có thể gây ra ùn tắc nhân tạo.
- Kịch bản nút ưu tiên (Priority/Right-of-Way) thiết lập mốc đối chuẩn (Unsignalized Baseline)
  để đánh giá chính xác mức độ cải thiện của các thuật toán điều khiển đèn (Fixed-time, Actuated, MARL).
"""

import sys
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import argparse

# Đảm bảo import config từ thư mục gốc macro_traffic_crawler nếu cần
_SCRIPT_DIR = Path(__file__).resolve().parent
_MODULE_ROOT = _SCRIPT_DIR.parent
for p in [_SCRIPT_DIR, _MODULE_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def count_junction_types(net_file: Path) -> dict:
    """Đếm số lượng các loại nút giao trong file .net.xml."""
    counts = {}
    try:
        context = ET.iterparse(net_file, events=("end",))
        for event, elem in context:
            if elem.tag == "junction":
                jtype = elem.attrib.get("type", "unknown")
                counts[jtype] = counts.get(jtype, 0) + 1
                elem.clear()
            elif elem.tag == "tlLogic":
                counts["tlLogic_count"] = counts.get("tlLogic_count", 0) + 1
                elem.clear()
    except Exception as e:
        print(f"[!] Cảnh báo đọc XML: {e}")
    return counts

def find_sumo_binary(binary_name: str = "netconvert") -> str:
    """Tìm đường dẫn thực thi của công cụ SUMO."""
    which_bin = shutil.which(binary_name)
    if which_bin:
        return which_bin
    
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home:
        candidate = Path(sumo_home) / "bin" / f"{binary_name}.exe"
        if candidate.exists():
            return str(candidate)
        candidate_nix = Path(sumo_home) / "bin" / binary_name
        if candidate_nix.exists():
            return str(candidate_nix)

    # Các vị trí cài đặt mặc định trên Windows
    default_win_path = Path("C:/Program Files (x86)/Eclipse/Sumo/bin") / f"{binary_name}.exe"
    if default_win_path.exists():
        return str(default_win_path)
    
    raise FileNotFoundError(f"Không tìm thấy công cụ SUMO '{binary_name}'. Hãy kiểm tra biến môi trường SUMO_HOME.")

def build_priority_scenario(
    input_net_path: Path,
    output_dir: Path,
    output_net_name: str = "q1_map_priority.net.xml",
    route_file_source: Path = None,
    vtypes_file_source: Path = None,
    begin_time: int = 0,
    end_time: int = 22603,
    step_length: float = 1.0,
    lateral_resolution: float = 0.8
) -> Path:
    """
    Chuyển đổi net.xml sang priority và tạo kịch bản sumocfg hoàn chỉnh.
    """
    print("=" * 80)
    print("KHỞI TẠO KỊCH BẢN MẠNG LƯỚI ƯU TIÊN (PRIORITY UNSIGNALIZED SCENARIO)")
    print("=" * 80)

    if not input_net_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file mạng lưới đầu vào: {input_net_path}")

    # Đếm số nút trước khi chuyển đổi
    before_stats = count_junction_types(input_net_path)
    print(f"[*] Mạng lưới gốc: {input_net_path.name}")
    print(f"    - Số nút giao có đèn (traffic_light): {before_stats.get('traffic_light', 0)}")
    print(f"    - Số chương trình đèn (tlLogic): {before_stats.get('tlLogic_count', 0)}")
    print(f"    - Số nút ưu tiên sẵn có (priority): {before_stats.get('priority', 0)}")

    # Tạo thư mục đầu ra
    output_dir.mkdir(parents=True, exist_ok=True)
    target_net_path = output_dir / output_net_name

    netconvert_bin = find_sumo_binary("netconvert")
    print(f"[*] Sử dụng netconvert: {netconvert_bin}")
    print(f"[*] Đang thực thi chuyển đổi mạng lưới (loại bỏ hoàn toàn TLS và tính toán lại Right-of-Way)...")

    cmd = [
        netconvert_bin,
        "-s", str(input_net_path.resolve()),
        "--tls.discard-loaded",
        "-o", str(target_net_path.resolve())
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    if result.returncode != 0:
        print("[!] Lỗi khi chạy netconvert:")
        print(result.stderr)
        raise RuntimeError(f"netconvert thất bại với mã lỗi {result.returncode}")

    # Đếm số nút sau khi chuyển đổi
    after_stats = count_junction_types(target_net_path)
    print(f"[+] Chuyển đổi thành công: {target_net_path.name}")
    print(f"    - Số nút giao có đèn còn lại: {after_stats.get('traffic_light', 0)}")
    print(f"    - Số chương trình đèn còn lại: {after_stats.get('tlLogic_count', 0)}")
    print(f"    - Tổng số nút ưu tiên hiện tại: {after_stats.get('priority', 0)}")

    # Xử lý đường dẫn tương đối cho .sumocfg
    # 1. Net file tương đối
    net_rel = target_net_path.name

    # 2. Route file
    if route_file_source and route_file_source.exists():
        # Sao chép route file vào kịch bản để độc lập hoặc tham chiếu
        route_target = output_dir / route_file_source.name
        if not route_target.exists():
            shutil.copy2(route_file_source, route_target)
            print(f"[+] Đã sao chép route file vào kịch bản: {route_target.name}")
        route_rel = route_target.name
    else:
        # Mặc định trỏ về kịch bản 6h
        route_rel = "../../sumo_scenarios/q1_20261020_6h/calibrated_routes_20261020_6h.rou.xml"

    # 3. Vtypes file
    if vtypes_file_source and vtypes_file_source.exists():
        vtypes_target = output_dir / vtypes_file_source.name
        if not vtypes_target.exists():
            shutil.copy2(vtypes_file_source, vtypes_target)
            print(f"[+] Đã sao chép vtypes file vào kịch bản: {vtypes_target.name}")
        vtypes_rel = vtypes_target.name
    else:
        vtypes_rel = "../../data/raw_data/vtypes.add.xml"

    # Tạo file simulation.sumocfg
    sumocfg_path = output_dir / "simulation.sumocfg"
    sumocfg_content = f"""<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <!-- Mạng lưới ưu tiên không đèn tín hiệu (Unsignalized Priority Network) -->
        <net-file value="{net_rel}"/>

        <!-- Tuyến đường lưu lượng thực tế đã hiệu chuẩn -->
        <route-files value="{route_rel}"/>

        <!-- Định nghĩa mô hình xe máy Việt Nam (Sublane Model) -->
        <additional-files value="{vtypes_rel}"/>
    </input>

    <time>
        <begin value="{begin_time}"/>
        <end value="{end_time}"/>
        <step-length value="{step_length}"/>
    </time>

    <processing>
        <!-- Kích hoạt Sublane Model: chia làn ảo {lateral_resolution}m cho xe máy luồn lách -->
        <lateral-resolution value="{lateral_resolution}"/>
        <collision.action value="warn"/>
        <time-to-teleport value="120"/>
    </processing>

    <output>
        <edgedata-output value="simulation_edgedata_priority.xml"/>
        <tripinfo-output value="tripinfo_priority.xml"/>
    </output>

    <report>
        <verbose value="false"/>
        <no-step-log value="true"/>
    </report>
</configuration>
"""
    with open(sumocfg_path, "w", encoding="utf-8") as f:
        f.write(sumocfg_content)
    print(f"[+] Đã tạo file cấu hình mô phỏng: {sumocfg_path}")

    # Tạo file README trong kịch bản
    readme_path = output_dir / "README.md"
    readme_content = f"""# Kịch Bản SUMO Không Đèn Tín Hiệu (Unsignalized Priority Scenario)

Kịch bản này chuyển toàn bộ {before_stats.get('traffic_light', 0)} nút giao đèn tín hiệu sang cơ chế nút ưu tiên (Priority Junctions) tuân theo quyền ưu tiên hình học và cấp đường TCVN 104:2007.

## Cấu trúc kịch bản:
- `{target_net_path.name}`: Mạng lưới không đèn tín hiệu.
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
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("=" * 80)
    print(f"[V] KỊCH BẢN ĐÃ SẴN SÀNG TẠI: {output_dir}")
    print(f"    Lệnh chạy GUI:  sumo-gui -c {sumocfg_path}")
    print("=" * 80)
    return sumocfg_path

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    default_input_net = project_root / "data" / "raw_data" / "q1_map.net.xml"
    default_output_dir = project_root / "sumo_scenarios" / "q1_priority_unsignalized"
    default_route = project_root / "sumo_scenarios" / "q1_20261020_6h" / "calibrated_routes_20261020_6h.rou.xml"
    default_vtypes = project_root / "data" / "raw_data" / "vtypes.add.xml"

    parser = argparse.ArgumentParser(description="Chuyển đổi mạng lưới SUMO sang Priority và tạo kịch bản mới.")
    parser.add_argument("--input-net", type=Path, default=default_input_net, help="Đường dẫn file .net.xml gốc")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir, help="Thư mục kịch bản đầu ra")
    parser.add_argument("--net-name", type=str, default="q1_map_priority.net.xml", help="Tên file .net.xml mới")
    parser.add_argument("--routes", type=Path, default=default_route, help="Đường dẫn file route (.rou.xml)")
    parser.add_argument("--vtypes", type=Path, default=default_vtypes, help="Đường dẫn file vtypes (.add.xml)")
    parser.add_argument("--end-time", type=int, default=22603, help="Thời gian kết thúc mô phỏng (giây)")
    parser.add_argument("--step-length", type=float, default=0.2, help="Độ dài bước mô phỏng (giây, chuẩn hóa 0.2s theo tau=0.6s)")
    parser.add_argument("--lateral-resolution", type=float, default=0.25, help="Độ phân giải Sublane (mét, chuẩn hóa 0.25m)")

    args = parser.parse_args()
    build_priority_scenario(
        input_net_path=args.input_net,
        output_dir=args.output_dir,
        output_net_name=args.net_name,
        route_file_source=args.routes,
        vtypes_file_source=args.vtypes,
        end_time=args.end_time,
        step_length=args.step_length,
        lateral_resolution=args.lateral_resolution
    )
