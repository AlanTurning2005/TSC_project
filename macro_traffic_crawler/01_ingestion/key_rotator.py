"""
key_rotator.py
Quan ly va xoay vong nhieu TomTom API Keys tu dong:
1. Theo doi so luong request da su dung cua tung key trong ngay.
2. Tu dong chuyen key khi gap HTTP 403 (Het quota) hoac cham nguong an toan.
3. Tu dong reset quota vao 07:00 sang gio Viet Nam (00:00 UTC).
4. Luu vet trang thai ra crawler_state.json tranh mat du lieu khi khoi dong lai.
"""

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

class KeyRotator:
    MAX_REQUESTS_PER_DAY = 2480  # Chừa 20 request dự phòng trước ngưỡng 2500

    def __init__(self, keys: List[str], state_file: Path, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.state_file = state_file
        
        if self.mock_mode or not keys:
            # Nếu chạy mock, sinh 5 mock keys giả lập
            self.keys = [f"MOCK_KEY_{i+1}" for i in range(5)]
        else:
            self.keys = keys

        self.current_key_idx = 0
        self.usage_data = self._load_or_init_state()

    def _get_utc_date_str(self) -> str:
        """Lay ngay theo chuan UTC (TomTom reset quota luc 00:00 UTC = 07:00 AM VN)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_or_init_state(self) -> Dict[str, Any]:
        """Doc trang thai tu file JSON hoac khoi tao moi neu qua ngay moi theo gio UTC."""
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
                
                # Kiem tra neu da sang ngay moi theo gio UTC (sau 7h sang VN)
                if state.get("utc_date") != utc_today:
                    print(f"[*] Da sang ngay moi theo UTC ({utc_today}). Reset quota cho toan bo {len(self.keys)} keys.")
                    return default_state
                
                # Dong bo danh sach keys neu co thay doi
                for k in self.keys:
                    if k not in state["keys_usage"]:
                        state["keys_usage"][k] = 0
                
                self.current_key_idx = state.get("active_key_index", 0)
                return state
            except Exception as e:
                print(f"[!] Loi khi doc state file ({e}). Khoi tao trang thai moi.")
        
        return default_state

    def _save_state(self):
        """Luu trang thai su dung vao file JSON."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.usage_data["utc_date"] = self._get_utc_date_str()
        self.usage_data["active_key_index"] = self.current_key_idx
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.usage_data, f, indent=2, ensure_ascii=False)

    def check_utc_day_reset(self):
        """Kiem tra va reset neu da qua 00:00 UTC (7h sang VN)."""
        utc_today = self._get_utc_date_str()
        if self.usage_data.get("utc_date") != utc_today:
            print(f"\n[RESET] 07:00 AM Gio VN (00:00 UTC) - Reset han ngach cho tat ca {len(self.keys)} API Keys!")
            self.usage_data["utc_date"] = utc_today
            self.usage_data["keys_usage"] = {k: 0 for k in self.keys}
            self.usage_data["exhausted_keys"] = []
            self.current_key_idx = 0
            self._save_state()

    def get_active_key(self) -> Optional[str]:
        """Lay key kha dung hien tai. Neu key hien tai het quota, tu dong tim key tiep theo."""
        self.check_utc_day_reset()

        # Tim key chua bi can kiet
        attempts = 0
        while attempts < len(self.keys):
            key = self.keys[self.current_key_idx]
            used = self.usage_data["keys_usage"].get(key, 0)
            is_exhausted = key in self.usage_data["exhausted_keys"]

            if not is_exhausted and used < self.MAX_REQUESTS_PER_DAY:
                return key
            
            # Neu key da can kiet hoac qua nguong, danh dau va chuyen tiep
            if key not in self.usage_data["exhausted_keys"]:
                self.usage_data["exhausted_keys"].append(key)
                print(f"[!] Key #{self.current_key_idx+1} ({key[:8]}...) da su dung {used}/{self.MAX_REQUESTS_PER_DAY}. Chuyen sang key tiep theo.")

            self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
            attempts += 1

        print("[ALERT] TAT CA CAC API KEYS DEU DA HET QUOTA CHO NGAY HOM NAY!")
        return None

    def record_success(self, key: str):
        """Ghi nhan 1 request thanh cong."""
        self.usage_data["keys_usage"][key] = self.usage_data["keys_usage"].get(key, 0) + 1
        self._save_state()

    def mark_exhausted(self, key: str, reason: str = "403 Forbidden"):
        """Danh dau key bi loi het quota tu server TomTom va lap tuc chuyen key."""
        print(f"[!] Server TomTom bao key {key[:8]}... bi can kiet: {reason}")
        if key not in self.usage_data["exhausted_keys"]:
            self.usage_data["exhausted_keys"].append(key)
        
        # Chuyen con tro sang key tiep theo
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        self._save_state()

    def print_summary(self):
        """In tong quan su dung cac keys."""
        print("\n--- TRANG THAI SU DUNG API KEYS ---")
        for i, k in enumerate(self.keys):
            used = self.usage_data["keys_usage"].get(k, 0)
            status = "DA HET" if k in self.usage_data["exhausted_keys"] else "KHA DUNG"
            print(f"  Key #{i+1} [{k[:8]}...]: {used}/{self.MAX_REQUESTS_PER_DAY} reqs ({status})")
        print(f"  Tong da dung: {sum(self.usage_data['keys_usage'].values())} reqs")
        print("------------------------------------\n")
