import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env từ thư mục macro_traffic_crawler hoặc thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

# TomTom Developer API Key
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "YOUR_TOMTOM_API_KEY")

# TomTom Traffic API Endpoints
TOMTOM_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# Cấu hình Bounding Box (Mặc định lấy từ map.osm trong raw_data: khu vực Q.5/Q.1 TP.HCM)
DEFAULT_BBOX = {
    "min_lat": 10.7546940,
    "min_lon": 106.6761090,
    "max_lat": 10.7614710,
    "max_lon": 106.6887470
}

# Cấu hình đường dẫn lưu trữ dữ liệu
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
POINTS_FILE = DATA_DIR / "sampling_points.csv"

# Đường dẫn tham chiếu đến dữ liệu mạng lưới hiện có trong dự án
NETWORK_XML_PATH = BASE_DIR.parent / "data" / "raw_data" / "my_network.net.xml"
OSM_MAP_PATH = BASE_DIR.parent / "data" / "raw_data" / "map.osm"

# Cấu hình crawl
CRAWL_INTERVAL_SECONDS = int(os.getenv("CRAWL_INTERVAL_SECONDS", "300"))  # 5 phút crawl 1 lần
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "0.2"))  # Tránh vượt rate limit
