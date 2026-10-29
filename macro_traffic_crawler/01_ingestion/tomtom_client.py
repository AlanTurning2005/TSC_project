"""
tomtom_client.py
Client ket noi TomTom Traffic Flow API (Flow Segment Data),
co co che retry, rate-limiting, error handling va mock-mode khi chua co API key.
"""

import sys
import time
import random
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Đảm bảo import config từ thư mục gốc macro_traffic_crawler
_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from config import TOMTOM_API_KEY, TOMTOM_FLOW_URL, REQUEST_DELAY_SECONDS

class QuotaExceededError(Exception):
    """Ngoại lệ khi API Key hết quota hoặc bị chặn 403."""
    pass

class TomTomTrafficClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TOMTOM_API_KEY
        self.is_mock = (not self.api_key or self.api_key in ("YOUR_TOMTOM_API_KEY", "MOCK"))
        if self.is_mock:
            print("[WARN] TOMTOM_API_KEY chua duoc cau hinh trong .env. Client se hoat dong o che do MOCK TEST.")

    def get_flow_segment(self, lat: float, lon: float, api_key: Optional[str] = None, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Goi Flow Segment Data API cho toa do (lat, lon).
        Tra ve dict chua cac macro traffic features va raw payload.
        Neu api_key duoc truyen vao, se uu tien su dung thay vi self.api_key.
        """
        active_key = api_key or self.api_key
        if self.is_mock or active_key.startswith("MOCK_KEY"):
            return self._mock_flow_data(lat, lon)

        params = {
            "point": f"{lat},{lon}",
            "unit": "KMPH",
            "key": active_key,
            "thickness": 10
        }

        for attempt in range(1, max_retries + 1):
            try:
                time.sleep(REQUEST_DELAY_SECONDS)
                response = requests.get(TOMTOM_FLOW_URL, params=params, timeout=10)

                if response.status_code == 200:
                    raw_data = response.json()
                    flow = raw_data.get("flowSegmentData", {})
                    return self._parse_flow_data(lat, lon, flow, raw_data)

                elif response.status_code == 403:
                    # Hết quota hoặc key không hợp lệ
                    raise QuotaExceededError(f"HTTP 403: {response.text[:100]}")

                elif response.status_code == 429:
                    wait_time = attempt * 2
                    print(f"[!] Rate limit (429). Cho {wait_time}s truoc khi thu lai lan {attempt}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    print(f"[!] Loi API ({response.status_code}): {response.text[:100]}")
                    return None

            except QuotaExceededError:
                raise
            except Exception as e:
                print(f"[!] Ngoai le khi goi TomTom API ({attempt}/{max_retries}): {e}")
                time.sleep(1)

        return None

    def _parse_flow_data(self, lat: float, lon: float, flow: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Chuan hoa cac features vi mo tu response TomTom."""
        curr_speed = float(flow.get("currentSpeed", 0.0))
        free_speed = float(flow.get("freeFlowSpeed", max(curr_speed, 1.0)))
        curr_time = float(flow.get("currentTravelTime", 0.0))
        free_time = float(flow.get("freeFlowTravelTime", curr_time))

        delay = max(0.0, curr_time - free_time)
        congestion_index = max(0.0, min(1.0, (free_speed - curr_speed) / free_speed)) if free_speed > 0 else 0.0

        return {
            "query_lat": lat,
            "query_lon": lon,
            "frc": flow.get("frc", "FRC0"),
            "current_speed": curr_speed,
            "free_flow_speed": free_speed,
            "current_travel_time": curr_time,
            "free_flow_travel_time": free_time,
            "delay_seconds": delay,
            "congestion_index": round(congestion_index, 4),
            "confidence": flow.get("confidence", 1.0),
            "road_closure": flow.get("roadClosure", False),
            "coordinates": flow.get("coordinates", {}).get("coordinate", []),
            "raw_response": raw_data
        }

    def _mock_flow_data(self, lat: float, lon: float) -> Dict[str, Any]:
        """Du lieu gia lap dung chuan schema TomTom phuc vu test pipeline offline."""
        free_speed = round(random.uniform(40.0, 60.0), 1)
        # Gia lap tinh trang gio cao diem / binh thuong
        speed_factor = random.uniform(0.35, 0.95)
        curr_speed = round(free_speed * speed_factor, 1)
        free_time = round(random.uniform(20.0, 60.0), 1)
        curr_time = round(free_time * (free_speed / max(curr_speed, 1.0)), 1)
        delay = round(curr_time - free_time, 1)
        congestion = round((free_speed - curr_speed) / free_speed, 4)

        return {
            "query_lat": lat,
            "query_lon": lon,
            "frc": random.choice(["FRC1", "FRC2", "FRC3"]),
            "current_speed": curr_speed,
            "free_flow_speed": free_speed,
            "current_travel_time": curr_time,
            "free_flow_travel_time": free_time,
            "delay_seconds": delay,
            "congestion_index": congestion,
            "confidence": 1.0,
            "road_closure": False,
            "coordinates": [{"latitude": lat, "longitude": lon}],
            "raw_response": {"flowSegmentData": {"currentSpeed": curr_speed, "mock": True}}
        }
