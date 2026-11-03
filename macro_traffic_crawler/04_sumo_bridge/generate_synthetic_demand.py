r"""
generate_synthetic_demand.py
=============================================================================
BỘ TẠO LỘ TRÌNH VÀ NHU CẦU TỔNG HỢP MÔ PHỎNG VI MÔ (SYNTHETIC DEMAND GENERATOR)
Dự án: MARL-TSC Mạng lưới Quận 1 & Quận 3, TP. Hồ Chí Minh

Tham chiếu phương pháp luận học thuật:
- macro_traffic_crawler/docs/SD_EVALUATION.md (Mục 1.3 & Mục II)
- macro_traffic_crawler/docs/HCMC_TRAFFIC_SPECIFICATIONS_AND_THEORY.md

CÁC THÔNG SỐ THIẾT KẾ ĐẶC THÙ ĐƯỢC CHUẨN HÓA (THEO HCMC_TRAFFIC_SPECIFICATIONS):
1. Cơ cấu phương tiện đô thị TP.HCM (Modal Split) & Vận tốc trần tự do thực địa:
   - 85% Xe máy (vClass="motorcycle", width=0.8m, length=1.8m, maxSpeed=9.72m/s [35 km/h], latAlignment="arbitrary", minGapLat=0.25m, tau=0.6s).
   - 12% Xe con / Taxi (vClass="passenger", width=1.8m, length=4.5m, maxSpeed=9.72m/s [35 km/h], minGapLat=0.60m, tau=1.0s).
   - 3% Xe buýt đô thị (vClass="bus", width=2.5m, length=10.5m, maxSpeed=8.33m/s [30 km/h], minGapLat=0.80m, tau=1.2s, lcSublane=0.0).
   (Tham chiếu: Dung et al. 2015, Minh et al. 2005, Vu & Preston 2023, TCVN 13592:2022).
2. Quy luật nạp xe biên vào lõi trung tâm (Commuter Inflow / Through-Traffic):
   - --fringe-factor 8.0: Tăng xác suất nạp xe từ các cửa ngõ biên (Phú Nhuận, Bình Thạnh, Q3, Q4)
     đổ vào trung tâm Quận 1 lên gấp 8 lần so with các đường nhánh nội bộ.
   - --min-distance 400.0: Loại bỏ các chuyến đi vi mô ngắn dưới 400m (chống kẹt cục bộ trong hẻm).
   - --speed-exponent 1.0: Ưu tiên phân bổ dòng xe vào các trục hành lang lớn (Điện Biên Phủ, NKKN, Pasteur).
   - --validate & --remove-loops: Bảo đảm tính liên thông và triệt tiêu các vòng lặp phi logic.
3. Kỹ thuật chia làn phụ SUMO Sublane & Ổn định số học:
   - Kích hoạt --lateral-resolution 0.25 trong tệp .sumocfg (khớp 1:1 với minGapLat 0.25m của xe máy).
   - Kích hoạt --step-length 0.2 trong tệp .sumocfg (đảm bảo tau/delta_t = 0.6/0.2 = 3 nguyên số).
=============================================================================
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Union, Dict, Any

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def find_sumo_tools_dir() -> Path:
    """Tìm thư mục chứa công cụ của SUMO (tools/randomTrips.py)."""
    # 1. Kiểm tra SUMO_HOME
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home and (Path(sumo_home) / "tools" / "randomTrips.py").exists():
        return Path(sumo_home) / "tools"

    # 2. Kiểm tra từ đường dẫn sumo binary
    sumo_bin = shutil.which("sumo")
    if sumo_bin:
        bin_path = Path(sumo_bin).resolve()
        tools_candidate = bin_path.parent.parent / "tools"
        if (tools_candidate / "randomTrips.py").exists():
            return tools_candidate

    # 3. Đường dẫn mặc định Windows
    win_default = Path("C:/Program Files (x86)/Eclipse/Sumo/tools")
    if (win_default / "randomTrips.py").exists():
        return win_default

    raise FileNotFoundError("Không tìm thấy công cụ SUMO 'randomTrips.py'. Vui lòng thiết lập biến môi trường SUMO_HOME!")


def generate_synthetic_routes(
    net_file: Union[str, Path],
    output_rou_file: Union[str, Path],
    vtypes_file: Optional[Union[str, Path]] = None,
    insertion_rate_vps: float = 2.0,
    begin_time: float = 0.0,
    end_time: float = 3600.0,
    fringe_factor: float = 8.0,
    min_distance: float = 400.0,
    speed_exponent: float = 1.0,
    seed: int = 42,
    verbose: bool = False,
) -> Path:
    r"""
    Sinh tệp lộ trình (.rou.xml) chuẩn hóa cho mạng lưới SUMO.

    Args:
        net_file: Tệp mạng lưới (.net.xml).
        output_rou_file: Tệp xuất lộ trình (.rou.xml).
        vtypes_file: Tệp định nghĩa phương tiện (mặc định lấy vtypes.add.xml).
        insertion_rate_vps: Tốc độ nạp xe toàn mạng \lambda (xe/giây).
                            Ví dụ 2.0 veh/s = 7.200 xe/giờ.
        begin_time: Thời điểm bắt đầu (giây).
        end_time: Thời điểm kết thúc (giây).
        fringe_factor: Hệ số nạp xe biên (mặc định 8.0).
        min_distance: Khoảng cách tối thiểu của chuyến đi (mét, mặc định 400.0).
        speed_exponent: Số mũ ưu tiên đường lớn (mặc định 1.0).
        seed: Hạt giống ngẫu nhiên (CRN).
        verbose: In chi tiết log SUMO.

    Returns:
        Path tới tệp .rou.xml vừa sinh.
    """
    tools_dir = find_sumo_tools_dir()
    random_trips_py = tools_dir / "randomTrips.py"

    net_path = Path(net_file).resolve()
    if not net_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file mạng lưới: {net_path}")

    out_rou_path = Path(output_rou_file).resolve()
    out_rou_path.parent.mkdir(parents=True, exist_ok=True)

    temp_trips_path = out_rou_path.parent / f"{out_rou_path.stem}.trips.xml"

    # Chu kỳ nạp xe giữa hai phương tiện liên tiếp: period = 1 / lambda
    insertion_rate_vps = max(0.05, float(insertion_rate_vps))
    period = 1.0 / insertion_rate_vps

    # Thuộc tính chuyến đi vi mô
    trip_attrs = 'type="hcmc_mixed" departLane="best" departSpeed="max"'

    # Xây dựng lệnh gọi randomTrips.py
    cmd = [
        sys.executable,
        str(random_trips_py),
        "-n", str(net_path),
        "-o", str(temp_trips_path),
        "-r", str(out_rou_path),
        "-b", str(begin_time),
        "-e", str(end_time),
        "-p", f"{period:.4f}",
        "--fringe-factor", str(fringe_factor),
        "--min-distance", str(min_distance),
        "--speed-exponent", str(speed_exponent),
        "--seed", str(seed),
        "--validate",
        "--remove-loops",
        "-t", trip_attrs,
    ]

    # Nếu có tệp vtypes, thêm vào duarouter
    if vtypes_file:
        vt_path = Path(vtypes_file).resolve()
        if vt_path.exists():
            cmd.extend(["-a", str(vt_path)])

    if verbose:
        print(f"[*] Thực thi lệnh sinh lộ trình: {' '.join(cmd)}")

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Lỗi khi chạy randomTrips.py:\n{res.stderr}\n{res.stdout}")

    if not out_rou_path.exists():
        raise FileNotFoundError(f"randomTrips.py hoàn tất nhưng không tìm thấy tệp {out_rou_path}!")

    # Đếm số lượng xe đã sinh
    # (Đọc thẻ <vehicle> trong tệp .rou.xml)
    veh_count = 0
    with open(out_rou_path, "r", encoding="utf-8") as f:
        for line in f:
            if "<vehicle " in line:
                veh_count += 1

    print(f"[+] Đã sinh thành công {veh_count} phương tiện trong tệp: {out_rou_path.name}")
    print(f"    • Tốc độ nạp λ: {insertion_rate_vps:.2f} xe/s (~{insertion_rate_vps * 3600:.0f} xe/h)")
    print(f"    • Khung thời gian: [{begin_time}s, {end_time}s] (Thời lượng: {end_time - begin_time}s)")
    print(f"    • Fringe Factor: {fringe_factor} | Min Distance: {min_distance}m | Seed: {seed}")

    return out_rou_path


def main():
    parser = argparse.ArgumentParser(description="Sinh nhu cầu giao thông tổng hợp chuẩn hóa (Synthetic Demand Generator)")
    parser.add_argument("--net-file", type=str, default="sumo_scenarios/q1_priority_unsignalized/q1_map_priority.net.xml",
                        help="Đường dẫn tệp .net.xml")
    parser.add_argument("--output-rou", type=str, default="sumo_scenarios/q1_priority_unsignalized/calibrated_priority_routes.rou.xml",
                        help="Đường dẫn xuất tệp .rou.xml")
    parser.add_argument("--vtypes-file", type=str, default="sumo_scenarios/q1_priority_unsignalized/vtypes.add.xml",
                        help="Đường dẫn tệp vtypes.add.xml")
    parser.add_argument("--rate", type=float, default=2.0,
                        help="Tốc độ nạp xe toàn mạng (xe/giây, mặc định 2.0 = 7200 xe/h)")
    parser.add_argument("--begin", type=float, default=0.0, help="Thời điểm bắt đầu (giây)")
    parser.add_argument("--end", type=float, default=3600.0, help="Thời điểm kết thúc (giây)")
    parser.add_argument("--fringe-factor", type=float, default=8.0, help="Hệ số nạp xe biên (mặc định 8.0)")
    parser.add_argument("--min-distance", type=float, default=400.0, help="Khoảng cách tối thiểu của chuyến đi (mét)")
    parser.add_argument("--speed-exponent", type=float, default=1.0, help="Số mũ ưu tiên đường lớn (mặc định 1.0)")
    parser.add_argument("--seed", type=int, default=42, help="Hạt giống ngẫu nhiên")
    parser.add_argument("--verbose", action="store_true", help="In chi tiết tiến trình")

    args = parser.parse_args()

    generate_synthetic_routes(
        net_file=args.net_file,
        output_rou_file=args.output_rou,
        vtypes_file=args.vtypes_file,
        insertion_rate_vps=args.rate,
        begin_time=args.begin,
        end_time=args.end,
        fringe_factor=args.fringe_factor,
        min_distance=args.min_distance,
        speed_exponent=args.speed_exponent,
        seed=args.seed,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
