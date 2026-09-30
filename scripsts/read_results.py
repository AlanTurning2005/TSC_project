import os
import xml.etree.ElementTree as ET
import pandas as pd

# Xác định đường dẫn gốc TSC_project
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

xml_file = os.path.join(BASE_DIR, "sumo_scenarios", "HZ", "tripinfo.xml")

if not os.path.exists(xml_file):
  raise FileNotFoundError(
      f"Không tìm thấy file: {xml_file}. Hãy chạy mô phỏng với cờ"
      " --tripinfo-output trước!"
  )

tree = ET.parse(xml_file)
root = tree.getroot()

data = []
for trip in root.findall("tripinfo"):
  data.append({
      "id": trip.get("id"),
      "duration": float(trip.get("duration")),
      "waitingTime": float(trip.get("waitingTime")),
      "timeLoss": float(trip.get("timeLoss")),
      "waitingCount": int(trip.get("waitingCount")),
  })

df = pd.DataFrame(data)

print("\n=== KẾT QUẢ THỐNG KÊ HÀNH TRÌNH XE (HZ SCENARIO) ===")
print(f"Tổng số xe hoàn thành lộ trình: {len(df)}")
print(f"Thời gian chờ trung bình (Mean Waiting Time): {df['waitingTime'].mean():.2f} s")
print(f"Độ trễ trung bình (Mean Time Loss): {df['timeLoss'].mean():.2f} s")
print(f"Thời gian di chuyển trung bình (Mean Travel Time): {df['duration'].mean():.2f} s")
print("\nBảng phân phối chi tiết:")
print(df[["duration", "waitingTime", "timeLoss"]].describe())