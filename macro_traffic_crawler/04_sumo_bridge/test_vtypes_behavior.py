"""
test_vtypes_behavior.py
Module nhập cấu hình hành vi phương tiện (vTypes JSON),
tự động sinh file vtypes.add.xml, thực thi mô phỏng SUMO và
trích xuất các chỉ số hành vi định lượng (Vận tốc, Độ trễ, Luồn lách Sublane, Teleport)
kèm tùy chọn xem trực quan qua SUMO-GUI.

Hỗ trợ 2 chế độ:
- corridor: Kiểm thử nhanh trên hành lang mẫu 400m 2 làn (~3-5 giây).
- q1: Kiểm thử toàn diện trên mạng lưới Quận 1 thực tế (mặc định 1800s = 30 phút).
"""

import sys
import os
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import argparse
from typing import Dict, Any, Tuple

# Hỗ trợ Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent

def find_sumo_binary(binary_name: str = "sumo") -> str:
    """Tìm đường dẫn thực thi của công cụ SUMO hoặc SUMO-GUI."""
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

    default_win_path = Path("C:/Program Files (x86)/Eclipse/Sumo/bin") / f"{binary_name}.exe"
    if default_win_path.exists():
        return str(default_win_path)
    
    raise FileNotFoundError(f"Không tìm thấy công cụ SUMO '{binary_name}'. Hãy kiểm tra biến môi trường SUMO_HOME.")

def load_vtypes_config(config_path: Path) -> Dict[str, Any]:
    """Đọc file cấu hình JSON của vTypes."""
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file cấu hình: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_vtypes_xml(config_data: Dict[str, Any], output_path: Path) -> Path:
    """Tạo file XML vtypes.add.xml từ cấu hình JSON."""
    vtypes = config_data.get("vtypes", {})
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        '<additional xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/additional_file.xsd">',
        '    <!-- ============================================================================== -->',
        '    <!-- TỰ ĐỘNG SINH TỪ VTYPES_CONFIG.JSON: HÀNH VI XE HỖN HỢP TP.HCM (SUBLANE MODEL) -->',
        '    <!-- ============================================================================== -->',
        '    <vTypeDistribution id="hcmc_mixed">'
    ]

    for type_id, params in vtypes.items():
        lines.append(f'        <!-- Phân loại: {type_id.upper()} ({params.get("notes", "")}) -->')
        attr_parts = [f'id="{type_id}"']
        
        # Các thuộc tính cốt lõi
        for key, val in params.items():
            if key == "notes":
                continue
            attr_parts.append(f'{key}="{val}"')
            
        attr_str = " ".join(attr_parts)
        lines.append(f'        <vType {attr_str}/>\n')

    lines.append('    </vTypeDistribution>')
    lines.append('</additional>')

    xml_content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"[+] Đã tạo file vTypes XML thành công: {output_path}")
    return output_path

def build_mini_corridor_scenario(work_dir: Path, vtypes_xml_path: Path, duration: int = 120) -> Path:
    """Tạo kịch bản hành lang thử nghiệm ngắn 400m 2 làn để test siêu nhanh."""
    work_dir.mkdir(parents=True, exist_ok=True)
    netconvert_bin = find_sumo_binary("netconvert")

    # 1. Tạo node file
    nod_file = work_dir / "corridor.nod.xml"
    with open(nod_file, "w", encoding="utf-8") as f:
        f.write("""<nodes>
    <node id="N_start" x="0.0" y="0.0" type="priority"/>
    <node id="N_end" x="400.0" y="0.0" type="priority"/>
</nodes>""")

    # 2. Tạo edge file (2 làn xe, tốc độ 40 km/h)
    edg_file = work_dir / "corridor.edg.xml"
    with open(edg_file, "w", encoding="utf-8") as f:
        f.write("""<edges>
    <edge id="E_corridor" from="N_start" to="N_end" numLanes="2" speed="11.11"/>
</edges>""")

    # 3. Biên dịch net.xml
    net_file = work_dir / "corridor.net.xml"
    cmd_net = [
        netconvert_bin,
        "--node-files", str(nod_file),
        "--edge-files", str(edg_file),
        "-o", str(net_file)
    ]
    subprocess.run(cmd_net, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    # 4. Tạo flow route với dòng xe hỗn hợp (1800 veh/hour)
    rou_file = work_dir / "corridor.rou.xml"
    with open(rou_file, "w", encoding="utf-8") as f:
        f.write(f"""<routes>
    <flow id="flow_corridor" type="hcmc_mixed" begin="0" end="{duration}" vehsPerHour="1800" from="E_corridor" to="E_corridor" departPos="base" departSpeed="max" departLane="best"/>
</routes>""")

    # 5. Tạo sumocfg
    cfg_file = work_dir / "corridor.sumocfg"
    with open(cfg_file, "w", encoding="utf-8") as f:
        f.write(f"""<configuration>
    <input>
        <net-file value="{net_file.name}"/>
        <route-files value="{rou_file.name}"/>
        <additional-files value="{vtypes_xml_path.resolve()}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{duration}"/>
        <step-length value="0.5"/>
    </time>
    <processing>
        <lateral-resolution value="0.8"/>
        <collision.action value="warn"/>
        <time-to-teleport value="60"/>
    </processing>
</configuration>""")

    return cfg_file

def parse_behavior_metrics(tripinfo_xml: Path, summary_xml: Path, lanechange_xml: Path) -> Dict[str, Any]:
    """Phân tích các tệp XML đầu ra của SUMO để tính toán các chỉ số hành vi."""
    metrics = {
        "by_type": {},
        "overall": {
            "total_departed": 0,
            "total_arrived": 0,
            "mean_speed_kmh": 0.0,
            "mean_waiting_time_s": 0.0,
            "mean_time_loss_s": 0.0,
            "total_teleports": 0,
            "total_sublane_maneuvers": 0,
            "total_lane_changes": 0
        }
    }

    # 1. Phân tích tripinfo.xml
    if tripinfo_xml.exists():
        try:
            tree = ET.parse(tripinfo_xml)
            root = tree.getroot()
            
            speeds_by_type = {}
            waits_by_type = {}
            timeloss_by_type = {}
            counts_by_type = {}

            all_speeds = []
            all_waits = []
            all_losses = []

            for trip in root.findall("tripinfo"):
                vtype = trip.attrib.get("vType", "unknown").split("@")[0]  # Tách ID phân phối
                duration = float(trip.attrib.get("duration", 0))
                route_length = float(trip.attrib.get("routeLength", 0))
                waiting_time = float(trip.attrib.get("waitingTime", 0))
                time_loss = float(trip.attrib.get("timeLoss", 0))

                speed_kmh = (route_length / duration * 3.6) if duration > 0 else 0.0

                counts_by_type[vtype] = counts_by_type.get(vtype, 0) + 1
                speeds_by_type.setdefault(vtype, []).append(speed_kmh)
                waits_by_type.setdefault(vtype, []).append(waiting_time)
                timeloss_by_type.setdefault(vtype, []).append(time_loss)

                all_speeds.append(speed_kmh)
                all_waits.append(waiting_time)
                all_losses.append(time_loss)

            for vtype in counts_by_type:
                v_speeds = speeds_by_type[vtype]
                v_waits = waits_by_type[vtype]
                v_losses = timeloss_by_type[vtype]
                metrics["by_type"][vtype] = {
                    "count": counts_by_type[vtype],
                    "mean_speed_kmh": round(sum(v_speeds) / len(v_speeds), 2) if v_speeds else 0.0,
                    "mean_waiting_time_s": round(sum(v_waits) / len(v_waits), 2) if v_waits else 0.0,
                    "mean_time_loss_s": round(sum(v_losses) / len(v_losses), 2) if v_losses else 0.0
                }

            metrics["overall"]["total_arrived"] = len(all_speeds)
            if all_speeds:
                metrics["overall"]["mean_speed_kmh"] = round(sum(all_speeds) / len(all_speeds), 2)
                metrics["overall"]["mean_waiting_time_s"] = round(sum(all_waits) / len(all_waits), 2)
                metrics["overall"]["mean_time_loss_s"] = round(sum(all_losses) / len(all_losses), 2)

        except Exception as e:
            print(f"[!] Lỗi phân tích tripinfo: {e}")

    # 2. Phân tích summary.xml
    if summary_xml.exists():
        try:
            tree = ET.parse(summary_xml)
            root = tree.getroot()
            steps = root.findall("step")
            if steps:
                last_step = steps[-1]
                metrics["overall"]["total_departed"] = int(last_step.attrib.get("inserted", 0))
                metrics["overall"]["total_teleports"] = int(last_step.attrib.get("teleports", 0))
        except Exception as e:
            print(f"[!] Lỗi phân tích summary: {e}")

    # 3. Phân tích lanechange.xml (đo lường chuyển làn và tương tác cự ly ngang)
    if lanechange_xml.exists():
        try:
            tree = ET.parse(lanechange_xml)
            root = tree.getroot()
            changes_by_type = {}
            lateral_interactions = 0
            total_changes = len(root)

            for ch in root.findall("change"):
                vtype = ch.attrib.get("type", "unknown")
                changes_by_type[vtype] = changes_by_type.get(vtype, 0) + 1
                lat_gap = ch.attrib.get("latGap", "None")
                if lat_gap != "None" and lat_gap != "":
                    lateral_interactions += 1

            for vtype in metrics["by_type"]:
                metrics["by_type"][vtype]["lane_changes"] = changes_by_type.get(vtype, 0)

            metrics["overall"]["total_lane_changes"] = total_changes
            metrics["overall"]["lateral_interactions"] = lateral_interactions
        except Exception as e:
            print(f"[!] Lỗi phân tích lanechange: {e}")

    return metrics

def print_behavior_report(metrics: Dict[str, Any], duration: int, mode: str):
    """Hiển thị bảng báo cáo kết quả hành vi định lượng chuẩn học thuật."""
    print("\n" + "=" * 90)
    print(f"📊 BÁO CÁO ĐỊNH LƯỢNG HÀNH VI PHƯƠNG TIỆN VI MÔ (VTYPES EVALUATION REPORT)")
    print(f"   Kịch bản kiểm thử: {mode.upper()} | Thời gian mô phỏng: {duration}s ({duration/60:.1f} phút)")
    print("=" * 90)

    print("\n1. THỐNG KÊ CHI TIẾT THEO LOẠI PHƯƠNG TIỆN:")
    print("-" * 90)
    print(f"{'Loại xe (vType)':<16} | {'Số xe hoàn thành':<16} | {'Vận tốc TB (km/h)':<18} | {'Thời gian chờ (s)':<18} | {'Chuyển làn':<10}")
    print("-" * 90)

    by_type = metrics.get("by_type", {})
    if by_type:
        for vtype, data in by_type.items():
            print(f"{vtype:<16} | {data.get('count', 0):<16} | {data.get('mean_speed_kmh', 0.0):<18} | {data.get('mean_waiting_time_s', 0.0):<18} | {data.get('lane_changes', 0):<10}")
    else:
        print("  (Chưa có phương tiện hoàn thành lộ trình hoặc hành trình dở dang)")
    print("-" * 90)

    ov = metrics.get("overall", {})
    print("\n2. CHỈ SỐ TOÀN MẠNG LƯỚI & TƯƠNG TÁC DÒNG XE:")
    print("-" * 90)
    print(f"• Tổng số xe đã nạp vào mạng lưới (Departed):      {ov.get('total_departed', 0):,}")
    print(f"• Tổng số xe đã hoàn thành lộ trình (Arrived):     {ov.get('total_arrived', 0):,}")
    print(f"• Vận tốc trung bình toàn mạng:                     {ov.get('mean_speed_kmh', 0.0)} km/h")
    print(f"• Độ trễ dừng chờ trung bình (Mean Waiting Time):   {ov.get('mean_waiting_time_s', 0.0)} s")
    print(f"• Thời gian thất thoát trung bình (Mean Time Loss): {ov.get('mean_time_loss_s', 0.0)} s")
    print(f"• Tổng số lượt chuyển làn (Total Lane Changes):     {ov.get('total_lane_changes', 0):,} lần")
    print(f"• Tương tác cự ly ngang hẹp (Lateral Interactions): {ov.get('lateral_interactions', 0):,} lần")
    print(f"• Số vụ xe bị kẹt giải tỏa khẩn cấp (Teleports):    {ov.get('total_teleports', 0)}")
    print("=" * 90 + "\n")

def run_vtypes_behavior_test(
    config_file: Path,
    mode: str = "q1",
    duration: int = 1800,
    use_gui: bool = False,
    net_file: Path = None,
    routes_file: Path = None,
    output_dir: Path = None
) -> Dict[str, Any]:
    """Điều phối toàn bộ quy trình kiểm thử hành vi phương tiện."""
    print("=" * 85)
    print("BẮT ĐẦU QUY TRÌNH KIỂM THỬ HÀNH VI PHƯƠNG TIỆN (VTYPES BEHAVIOR TEST)")
    print(f"• File cấu hình: {config_file}")
    print(f"• Chế độ kiểm thử: {mode} (Thời lượng: {duration}s / {duration/60:.1f} phút)")
    print(f"• Trực quan hóa GUI: {'BẬT (sumo-gui)' if use_gui else 'TẮT (chạy ngầm tốc độ cao)'}")
    print("=" * 85)

    config_data = load_vtypes_config(config_file)
    output_dir = output_dir or (_PROJECT_ROOT / "macro_traffic_crawler" / "data" / "behavior_reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Sinh file XML từ JSON
    vtypes_xml_path = output_dir / "tested_vtypes.add.xml"
    generate_vtypes_xml(config_data, vtypes_xml_path)

    # 2. Chuẩn bị file kịch bản chạy
    tripinfo_out = output_dir / f"tripinfo_{mode}.xml"
    summary_out = output_dir / f"summary_{mode}.xml"
    lanechange_out = output_dir / f"lanechange_{mode}.xml"

    # Xóa file kết quả cũ
    for f in [tripinfo_out, summary_out, lanechange_out]:
        if f.exists():
            f.unlink()

    binary_name = "sumo-gui" if use_gui else "sumo"
    sumo_bin = find_sumo_binary(binary_name)

    if mode == "corridor":
        work_corridor = output_dir / "mini_corridor"
        cfg_file = build_mini_corridor_scenario(work_corridor, vtypes_xml_path, duration=duration)
        cmd = [
            sumo_bin,
            "-c", str(cfg_file),
            "--tripinfo-output", str(tripinfo_out),
            "--tripinfo-output.write-unfinished", "true",
            "--summary-output", str(summary_out),
            "--lanechange-output", str(lanechange_out)
        ]
    else:
        # Mode Q1 (Mạng lưới Quận 1)
        net_path = net_file or (_PROJECT_ROOT / "sumo_scenarios" / "q1_priority_unsignalized" / "q1_map_priority.net.xml")
        if not net_path.exists():
            net_path = _PROJECT_ROOT / "data" / "raw_data" / "q1_map.net.xml"

        rou_path = routes_file or (_PROJECT_ROOT / "sumo_scenarios" / "q1_20261020_6h" / "calibrated_routes_20261020_6h.rou.xml")
        
        sim_defaults = config_data.get("simulation_defaults", {})
        lat_res = sim_defaults.get("lateral_resolution", 0.8)
        time_to_teleport = sim_defaults.get("time_to_teleport", 120)

        cmd = [
            sumo_bin,
            "-n", str(net_path),
            "-r", str(rou_path),
            "-a", str(vtypes_xml_path),
            "--begin", "0",
            "--end", str(duration),
            "--step-length", "1.0",
            "--lateral-resolution", str(lat_res),
            "--collision.action", "warn",
            "--time-to-teleport", str(time_to_teleport),
            "--tripinfo-output", str(tripinfo_out),
            "--tripinfo-output.write-unfinished", "true",
            "--summary-output", str(summary_out),
            "--lanechange-output", str(lanechange_out),
            "--no-step-log", "true"
        ]

    if use_gui:
        cmd.extend(["--start", "true", "--quit-on-end", "false"])

    print(f"[*] Đang thực thi mô phỏng: {' '.join(cmd[:6])} ...")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    
    if proc.returncode != 0 and not use_gui:
        print(f"[!] Mô phỏng báo lỗi:")
        print(proc.stderr[:500])

    # 3. Phân tích kết quả
    metrics = parse_behavior_metrics(tripinfo_out, summary_out, lanechange_out)
    print_behavior_report(metrics, duration, mode)

    # 4. Xuất file JSON báo cáo
    report_json_path = output_dir / f"behavior_metrics_{mode}.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"[+] Báo cáo chi tiết dạng JSON đã lưu tại: {report_json_path}")

    return metrics

if __name__ == "__main__":
    default_config = _SCRIPT_DIR / "vtypes_config.json"
    
    parser = argparse.ArgumentParser(description="Kiểm thử và đo lường hành vi phương tiện SUMO vi mô từ file cấu hình JSON.")
    parser.add_argument("--config", type=Path, default=default_config, help="Đường dẫn file cấu hình vtypes_config.json")
    parser.add_argument("--mode", type=str, choices=["corridor", "q1"], default="q1", help="Chế độ kiểm thử: corridor (hành lang test nhanh) hoặc q1 (mạng lưới Quận 1)")
    parser.add_argument("--duration", type=int, default=1800, help="Thời gian mô phỏng (giây). Mặc định 1800s = 30 phút")
    parser.add_argument("--gui", action="store_true", help="Bật giao diện trực quan SUMO-GUI")
    parser.add_argument("--net", type=Path, default=None, help="Tùy chọn chỉ định file mạng lưới .net.xml")
    parser.add_argument("--routes", type=Path, default=None, help="Tùy chọn chỉ định file lộ trình .rou.xml")

    args = parser.parse_args()
    
    # Nếu chạy corridor mà người dùng không chỉ định duration, dùng mặc định 120s
    test_duration = args.duration
    if args.mode == "corridor" and args.duration == 1800:
        test_duration = 120

    run_vtypes_behavior_test(
        config_file=args.config,
        mode=args.mode,
        duration=test_duration,
        use_gui=args.gui,
        net_file=args.net,
        routes_file=args.routes
    )
