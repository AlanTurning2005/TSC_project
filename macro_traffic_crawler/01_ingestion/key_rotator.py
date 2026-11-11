"""
key_rotator.py
Hệ thống Quản lý và Xoay vòng Nhiều TomTom API Keys với Cơ chế Quota Guard:
1. Theo dõi số lượng request đã sử dụng của từng key trong ngày (chặn trần an toàn 2.480 req/key).
2. Tự động reset hạn ngạch vào 07:00 sáng giờ Việt Nam (00:00 UTC).
3. Cơ chế Quota Guard (Ví dự phòng sáng sớm):
   - Mặc định bảo lưu 3.000 requests (hoặc tùy chỉnh) tuyệt đối không cho phép dùng vào ban ngày.
   - Khi lượng request còn lại trong toàn bộ pool chạm ngưỡng 3.000, tự động dừng cào ban ngày.
   - Đến đúng 06:00 sáng hôm sau, tự động mở khóa 3.000 requests này để cào từ 06:00 đến 07:00.
   - Đến 07:00 sáng (00:00 UTC), TomTom reset hạn ngạch mới 100%, vòng lặp lại tiếp tục.
4. Lưu vết trạng thái ra crawler_state.json tránh mất dữ liệu khi khởi động lại máy.
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta, time as dtime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

class KeyRotator:
    MAX_REQUESTS_PER_KEY = 2480  # Trần an toàn chừa 20 request đệm trước ngưỡng 2.500

    def __init__(
        self,
        keys: List[str],
        state_file: Path,
        reserve_requests: int = 3000,
        morning_start_hour: int = 6,
        morning_reset_hour: int = 7,
        mock_mode: bool = False
    ):
        self.mock_mode = mock_mode
        self.state_file = state_file
        self.reserve_requests = reserve_requests
        self.morning_start_hour = morning_start_hour
        self.morning_reset_hour = morning_reset_hour
        
        if self.mock_mode or not keys:
            self.keys = [f"MOCK_KEY_{i+1}" for i in range(5)]
        else:
            self.keys = keys

        self.current_key_idx = 0
        self.usage_data = self._load_or_init_state()

    def get_vn_now(self) -> datetime:
        """Lấy thời gian hiện tại theo múi giờ Việt Nam (UTC+7)."""
        return datetime.now(VN_TZ)

    def _get_utc_date_str(self) -> str:
        """Lấy ngày theo chuẩn UTC (TomTom reset quota lúc 00:00 UTC = 07:00 AM VN)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def is_morning_reserve_window(self) -> bool:
        """
        Kiểm tra xem hiện tại có đang nằm trong khung giờ dùng Quỹ Dự phòng Sáng sớm hay không.
        Mặc định: từ 06:00:00 đến trước 07:00:00 sáng giờ VN.
        """
        vn_time = self.get_vn_now().time()
        start = dtime(self.morning_start_hour, 0, 0)
        end = dtime(self.morning_reset_hour, 0, 0)
        return start <= vn_time < end

    def get_total_capacity(self) -> int:
        """Tổng dung lượng an toàn tối đa của toàn bộ các keys trong 1 ngày."""
        return len(self.keys) * self.MAX_REQUESTS_PER_KEY

    def get_total_used(self) -> int:
        """Tổng số requests đã sử dụng của toàn bộ keys trong ngày UTC hiện tại."""
        return sum(self.usage_data.get("keys_usage", {}).values())

    def get_remaining_pool(self) -> int:
        """Số requests còn lại chưa sử dụng trong toàn bộ pool."""
        return max(0, self.get_total_capacity() - self.get_total_used())

    def _load_or_init_state(self) -> Dict[str, Any]:
        """Đọc trạng thái từ file JSON hoặc khởi tạo mới nếu đã sang ngày mới theo giờ UTC."""
        utc_today = self._get_utc_date_str()
        
        default_state = {
            "utc_date": utc_today,
            "active_key_index": 0,
            "keys_usage": {k: 0 for k in self.keys},
            "exhausted_keys": []
        }

        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                
                # Kiểm tra nếu đã sang ngày mới theo giờ UTC (sau 7h sáng VN)
                if state.get("utc_date") != utc_today:
                    print(f"[*] Đã sang ngày mới theo UTC ({utc_today}). Reset quota cho toàn bộ {len(self.keys)} keys.")
                    return default_state
                
                # Đồng bộ danh sách keys nếu có thay đổi trong .env
                for k in self.keys:
                    if k not in state.get("keys_usage", {}):
                        state["keys_usage"][k] = 0
                
                self.current_key_idx = state.get("active_key_index", 0)
                return state
            except Exception as e:
                print(f"[!] Lỗi khi đọc state file ({e}). Khởi tạo trạng thái mới.")
        
        return default_state

    def _save_state(self):
        """Lưu trạng thái sử dụng vào file JSON."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        # LƯU Ý: Không được tự tiện gán self.usage_data["utc_date"] = self._get_utc_date_str() ở đây!
        # utc_date chỉ được cập nhật khi hàm check_utc_day_reset() hoặc force_reset() thực hiện xóa trắng hạn ngạch.
        self.usage_data["active_key_index"] = self.current_key_idx
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.usage_data, f, indent=2, ensure_ascii=False)

    def force_reset(self):
        """Buộc reset toàn bộ hạn ngạch của tất cả các keys về 0."""
        utc_today = self._get_utc_date_str()
        vn_now_str = self.get_vn_now().strftime("%H:%M:%S %d/%m/%Y")
        print(f"\n=======================================================")
        print(f"[RESET THỦ CÔNG] {vn_now_str} - Khởi tạo lại 100% cho {len(self.keys)} API Keys!")
        print(f"=======================================================\n")
        self.usage_data["utc_date"] = utc_today
        self.usage_data["keys_usage"] = {k: 0 for k in self.keys}
        self.usage_data["exhausted_keys"] = []
        self.current_key_idx = 0
        self._save_state()

    def check_utc_day_reset(self) -> bool:
        """Kiểm tra và tự động reset nếu đã qua 00:00 UTC (07:00 AM VN)."""
        utc_today = self._get_utc_date_str()
        if self.usage_data.get("utc_date") != utc_today:
            vn_now_str = self.get_vn_now().strftime("%H:%M:%S %d/%m/%Y")
            print(f"\n=======================================================")
            print(f"[RESET THÀNH CÔNG] {vn_now_str} (00:00 UTC) - TomTom đã nạp đầy Quota!")
            print(f"[*] Khởi tạo lại hạn ngạch mới 100% cho toàn bộ {len(self.keys)} API Keys.")
            print(f"=======================================================\n")
            self.usage_data["utc_date"] = utc_today
            self.usage_data["keys_usage"] = {k: 0 for k in self.keys}
            self.usage_data["exhausted_keys"] = []
            self.current_key_idx = 0
            self._save_state()
            return True
        return False

    def get_active_key(self) -> Optional[str]:
        """
        Lấy key khả dụng hiện tại với cơ chế kiểm soát Quota Guard:
        - Nếu ngoài khung 06:00 - 07:00 sáng mà quota còn lại <= reserve_requests:
          Kích hoạt Quota Guard (bảo vệ quỹ cho sáng mai) -> Trả về None.
        - Nếu trong khung 06:00 - 07:00 sáng: Mở khóa quỹ dự phòng, cho phép tiêu thụ.
        """
        self.check_utc_day_reset()

        in_morning_reserve = self.is_morning_reserve_window()
        total_remaining = self.get_remaining_pool()

        # Kiểm tra ngưỡng Quota Guard (chỉ áp dụng khi KHÔNG PHẢI khung sáng sớm 06:00 - 07:00)
        if not in_morning_reserve and total_remaining <= self.reserve_requests:
            print(f"\n[QUOTA GUARD ACTIVE] Đã chạm ngưỡng bảo lưu sáng hôm sau!")
            print(f"  + Hạn ngạch còn lại: {total_remaining} requests.")
            print(f"  + Ngưỡng bảo lưu bắt buộc: {self.reserve_requests} requests.")
            print(f"  + Hành động: Khóa cào ban ngày để bảo toàn nguyên vẹn cho khung 06:00 - 07:00 sáng mai.")
            return None

        # Tìm key chưa bị cạn kiệt trong danh sách
        attempts = 0
        while attempts < len(self.keys):
            key = self.keys[self.current_key_idx]
            used = self.usage_data["keys_usage"].get(key, 0)
            is_exhausted = key in self.usage_data["exhausted_keys"]

            if not is_exhausted and used < self.MAX_REQUESTS_PER_KEY:
                return key
            
            # Nếu key đã cạn kiệt, ghi nhận và chuyển key kế tiếp
            if key not in self.usage_data["exhausted_keys"]:
                self.usage_data["exhausted_keys"].append(key)
                print(f"[!] Key #{self.current_key_idx+1} ({key[:8]}...) đã dùng {used}/{self.MAX_REQUESTS_PER_KEY}. Chuyển sang key tiếp theo.")

            self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
            attempts += 1

        print("\n[ALERT] Toàn bộ các API keys trong pool đã cạn kiệt hạn ngạch!")
        return None

    def record_success(self, key: str):
        """Ghi nhận 1 request thành công và lưu trạng thái."""
        self.check_utc_day_reset()
        self.usage_data["keys_usage"][key] = self.usage_data["keys_usage"].get(key, 0) + 1
        self._save_state()

    def mark_exhausted(self, key: str, reason: str = "403 Forbidden"):
        """Đánh dấu key bị cạn kiệt từ phản hồi server TomTom và chuyển sang key kế tiếp."""
        print(f"[!] Server TomTom báo key {key[:8]}... bị cạn kiệt ({reason}).")
        if key not in self.usage_data["exhausted_keys"]:
            self.usage_data["exhausted_keys"].append(key)
        
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        self._save_state()

    def print_summary(self):
        """In bảng tổng quan trạng thái sử dụng của toàn bộ keys."""
        total_cap = self.get_total_capacity()
        total_used = self.get_total_used()
        remaining = self.get_remaining_pool()
        in_morning = self.is_morning_reserve_window()

        print("\n================ BÁO CÁO HẠN NGẠCH API KEYS ================")
        print(f" Thời gian VN (UTC+7): {self.get_vn_now().strftime('%H:%M:%S %d/%m/%Y')}")
        print(f" Ngày UTC hiện tại   : {self._get_utc_date_str()} (Reset vào 07:00 AM VN)")
        status_str = "ĐANG MỞ KHÓA VÍ SÁNG SỚM (06:00 - 07:00)" if in_morning else f"BAN NGÀY (Bảo lưu {self.reserve_requests} reqs)"
        print(f" Chế độ Quota Guard  : {status_str}")
        print("------------------------------------------------------------")
        for i, k in enumerate(self.keys):
            used = self.usage_data["keys_usage"].get(k, 0)
            status = "ĐÃ HẾT" if k in self.usage_data["exhausted_keys"] else "KHẢ DỤNG"
            print(f"  Key #{i+1:02d} [{k[:8]}...]: {used:4d}/{self.MAX_REQUESTS_PER_KEY} reqs ({status})")
        print("------------------------------------------------------------")
        print(f"  Tổng dung lượng Pool : {total_cap:5d} requests")
        print(f"  Tổng số đã tiêu thụ  : {total_used:5d} requests ({total_used/total_cap*100:.1f}%)")
        print(f"  Hạn ngạch còn lại    : {remaining:5d} requests")
        if not in_morning:
            usable_day = max(0, remaining - self.reserve_requests)
            print(f"  Khả dụng ban ngày    : {usable_day:5d} requests (Đã giữ lại {self.reserve_requests} cho sáng mai)")
        print("============================================================\n")
