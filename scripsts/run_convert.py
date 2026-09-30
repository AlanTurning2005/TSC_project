import os
import sys
import subprocess
from types import SimpleNamespace

# 1. Xác định đường dẫn gốc TSC_project
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
sys.path.append(BASE_DIR)

from tools import converter_v2

# Đường dẫn dữ liệu CityFlow HZ
DATA_DIR = os.path.join(BASE_DIR, "data_cityflow", "HZ")
road_path = os.path.join(DATA_DIR, "roadnet.json")
flow_path = os.path.join(DATA_DIR, "flow.json")

output_dir = os.path.join(BASE_DIR, "sumo_scenarios", "HZ")
os.makedirs(output_dir, exist_ok=True)

print(f">>> Đang đọc từ: {DATA_DIR}")
print(f">>> Thư mục xuất SUMO: {output_dir}")

# 2. Khởi tạo args với đúng các thuộc tính mà converter_v2.py yêu cầu
args = SimpleNamespace(
    or_cityflownet=road_path,
    or_cityflowflow=flow_path,
    or_cityflowtraffic=flow_path,  # Đồng bộ với tên hàm gốc
    sumonet="network",
    sumotraffic="flow",
    output_dir=output_dir,
    dataset="HZ",
)

# 3. Chạy chuyển đổi mạng và luồng
converter_v2.cityflow2sumo_net(args)
converter_v2.cityflow2sumo_flow(args)

# 4. Biên dịch mạng lưới hoàn chỉnh bằng netconvert
netconvert_cmd = [
    "netconvert",
    "--node-files",
    os.path.join(output_dir, "net.nod.xml"),
    "--edge-files",
    os.path.join(output_dir, "net.edg.xml"),
    "--connection-files",
    os.path.join(output_dir, "net.con.xml"),
    "--tllogic-files",
    os.path.join(output_dir, "net.tll.xml"),
    "-o",
    os.path.join(output_dir, "network.net.xml"),
    "--tls.discard-loaded",
    "false",
]

subprocess.run(netconvert_cmd, check=True)
print(">>> Chuyển đổi và biên dịch mạng lưới SUMO thành công!")