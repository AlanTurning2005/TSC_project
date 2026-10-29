import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env từ thư mục macro_traffic_crawler hoặc thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

# TomTom Developer API Keys (Hỗ trợ danh sách nhiều keys phân tách bởi dấu phẩy)
raw_keys = os.getenv("TOMTOM_API_KEYS", "")
valid_keys = [k.strip() for k in raw_keys.split(",") if k.strip() and not k.strip().startswith("#")]

single_key = os.getenv("TOMTOM_API_KEY", "").strip()
if single_key and not single_key.startswith("#") and single_key not in valid_keys:
    valid_keys.insert(0, single_key)

TOMTOM_API_KEYS = valid_keys
TOMTOM_API_KEY = TOMTOM_API_KEYS[0] if TOMTOM_API_KEYS else "YOUR_TOMTOM_API_KEY"

# TomTom Traffic API Endpoints
TOMTOM_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# Cấu hình Bounding Box (Lấy từ q1_map.osm: khu vực trung tâm Quận 1 & Hồ Con Rùa)
DEFAULT_BBOX = {
    "min_lat": 10.7752910,
    "min_lon": 106.6860220,
    "max_lat": 10.7820680,
    "max_lon": 106.6986610
}

# Cấu hình đường dẫn lưu trữ dữ liệu
MODULE_ROOT = BASE_DIR
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
METADATA_DIR = DATA_DIR / "metadata"

# Tệp metadata danh sách điểm đo & trạng thái crawler (ưu tiên thư mục metadata/)
POINTS_FILE = METADATA_DIR / "sampling_points.csv" if (METADATA_DIR / "sampling_points.csv").exists() else DATA_DIR / "sampling_points.csv"
STATE_FILE = METADATA_DIR / "crawler_state.json" if (METADATA_DIR / "crawler_state.json").exists() else DATA_DIR / "crawler_state.json"

# Đường dẫn tham chiếu đến dữ liệu mạng lưới hiện có trong dự án
NETWORK_XML_PATH = PROJECT_ROOT / "data" / "raw_data" / "q1_map.net.xml"
OSM_MAP_PATH = RAW_DATA_DIR / "q1_map.osm"

# Cấu hình crawl
CRAWL_INTERVAL_SECONDS = int(os.getenv("CRAWL_INTERVAL_SECONDS", "300"))  # 5 phút crawl 1 lần
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "0.2"))  # Tránh vượt rate limit
