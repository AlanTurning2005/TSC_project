"""Chạy mô phỏng Quận 1 với các sự cố ngẫu nhiên (uncertainty).

Đặt file này trong thư mục scripsts/ (cạnh run_convert.py). Ví dụ:

    python scripsts/run_uncertainty.py --baseline --seeds 1 2 3 --events 5 --kind mixed
    python scripsts/run_uncertainty.py --gui --seeds 1 --events 5 --kind breakdown --block full

Ba loại sự cố (kind):
    breakdown : một xe chết máy / tai nạn dừng giữa làn trong một khoảng thời gian.
                --block full   : xe rộng bằng cả làn, chắn hẳn làn đó.
                --block partial: xe con bình thường, xe máy vẫn luồn qua được (sublane).
    closure   : đóng một làn (cấm mọi loại xe) trong một khoảng thời gian.
                Với cạnh chỉ có 1 làn thì đây là đóng cả đường; nên bật --reroute.
    slow      : giảm tốc độ tối đa của cả cạnh (ngập nước, ổ gà, đám đông).
    mixed     : mỗi sự cố chọn ngẫu nhiên một trong ba loại trên.

Với --gui (hoặc --markers) mỗi sự cố có một chấm màu trên bản đồ: đỏ là xe chết máy,
cam là đóng làn, vàng là giảm tốc. Thời điểm và vị trí cũng được in ra terminal.

Khi đóng làm đứt route của một xe chưa vào mạng, SUMO loại xe đó (cột dropped trong kết quả).
Bật --reroute để xe tìm đường vòng thay vì bị loại.

Vị trí sự cố được chọn ngẫu nhiên có trọng số theo lưu lượng của calibrated_routes.rou.xml,
nên sự cố rơi vào các trục xe thực sự đi qua. Cùng một seed thì cùng một bộ sự cố.
"""

import argparse
import csv
import os
import random
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter

if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

import sumolib
import traci

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

BLOCKED_CLASSES = ["passenger", "motorcycle", "bus"]
KINDS = ["breakdown", "closure", "slow"]
METRICS = [
    "arrived",
    "waiting_end",
    "mean_duration",
    "mean_waiting",
    "mean_time_loss",
    "mean_speed",
    "teleports",
    "collisions",
    "dropped",
]


def read_cfg_paths(cfg_path):
    """Đọc đường dẫn net-file và route-files từ file .sumocfg."""
    cfg_dir = os.path.dirname(os.path.abspath(cfg_path))
    root = ET.parse(cfg_path).getroot()

    def get(tag):
        el = root.find(".//" + tag)
        if el is None:
            return []
        return [os.path.join(cfg_dir, p.strip()) for p in el.get("value").split(",")]

    return get("net-file")[0], get("route-files")


def edge_usage(route_files):
    """Đếm số xe đi qua mỗi cạnh dựa trên các thẻ <flow number=...>."""
    usage = Counter()
    for route_file in route_files:
        for _, el in ET.iterparse(route_file):
            if el.tag != "flow":
                continue
            number = int(el.get("number", "1"))
            route = el.find("route")
            if route is not None:
                for edge_id in route.get("edges").split():
                    usage[edge_id] += number
    return usage


def build_candidates(net, usage, min_length, weighting):
    ids, weights = [], []
    for edge_id, count in usage.items():
        if not net.hasEdge(edge_id):
            continue
        edge = net.getEdge(edge_id)
        if edge.getLength() < min_length or not edge.allows("passenger"):
            continue
        ids.append(edge_id)
        weights.append(count if weighting == "traffic" else 1)
    return ids, weights


def sample_events(rng, net, ids, weights, args, kinds):
    events = []
    t_lo = args.event_start_min
    t_hi = max(t_lo, args.end - args.event_start_margin)
    for i in range(args.events):
        edge_id = rng.choices(ids, weights=weights, k=1)[0]
        edge = net.getEdge(edge_id)
        length = edge.getLength()
        events.append({
            "id": i,
            "kind": rng.choice(kinds),
            "edge": edge_id,
            "lane_index": rng.randrange(edge.getLaneNumber()),
            "pos": round(rng.uniform(0.2 * length, 0.7 * length), 1),
            "start": round(rng.uniform(t_lo, t_hi), 1),
            "duration": round(rng.uniform(args.duration_min, args.duration_max), 1),
            "slow_speed": round(rng.uniform(args.slow_min, args.slow_max), 2),
        })
    events.sort(key=lambda e: e["start"])
    return events


def write_events(path, events):
    if not events:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(events[0].keys()))
        writer.writeheader()
        writer.writerows(events)


MARKER_COLORS = {
    "breakdown": (255, 0, 0, 255),
    "closure": (255, 128, 0, 255),
    "slow": (255, 220, 0, 255),
}


def add_marker(ev, net, lane_id):
    """Đặt một chấm màu (POI) lên bản đồ tại vị trí sự cố."""
    shape = net.getLane(lane_id).getShape()
    x, y = sumolib.geomhelper.positionAtShapeOffset(shape, ev["pos"])
    poi_id = "event_marker_%d" % ev["id"]
    traci.poi.add(
        poi_id, x, y, MARKER_COLORS[ev["kind"]],
        poiType=ev["kind"], layer=202, width=14, height=14,
    )
    return poi_id


def activate(ev, now, net, args):
    """Kích hoạt một sự cố tại thời điểm now. Trả về hàm khôi phục."""
    edge_id = ev["edge"]
    lane_index = ev["lane_index"]
    lane_id = "%s_%d" % (edge_id, lane_index)
    ev["end_time"] = now + ev["duration"]

    note = ""
    undo = None

    if ev["kind"] == "breakdown":
        vid = "obstacle_%d" % ev["id"]
        route_id = "obstacle_route_%d" % ev["id"]
        type_id = "obstacle_type_%d" % ev["id"]
        traci.vehicletype.copy("obstacle_base", type_id)
        if args.block == "full":
            traci.vehicletype.setWidth(type_id, net.getLane(lane_id).getWidth())
        traci.route.add(route_id, [edge_id])
        traci.vehicle.add(
            vid,
            route_id,
            typeID=type_id,
            depart="now",
            departLane=str(lane_index),
            departPos=str(ev["pos"]),
            departSpeed="0",
        )
        traci.vehicle.setColor(vid, (255, 0, 0, 255))
        traci.vehicle.setLaneChangeMode(vid, 0)
        traci.vehicle.setStop(
            vid,
            edge_id,
            pos=ev["pos"] + 8.0,
            laneIndex=lane_index,
            duration=ev["duration"],
        )
        note = "xe %s" % vid

    elif ev["kind"] == "closure":
        original = traci.lane.getAllowed(lane_id)
        traci.lane.setDisallowed(lane_id, BLOCKED_CLASSES)

        def undo():
            traci.lane.setAllowed(lane_id, original)

    elif ev["kind"] == "slow":
        lane_ids = [lane.getID() for lane in net.getEdge(edge_id).getLanes()]
        originals = [(lid, traci.lane.getMaxSpeed(lid)) for lid in lane_ids]
        for lid in lane_ids:
            traci.lane.setMaxSpeed(lid, ev["slow_speed"])
        note = "tốc độ tối đa còn %.1f m/s" % ev["slow_speed"]

        def undo():
            for lid, speed in originals:
                traci.lane.setMaxSpeed(lid, speed)

    marker = add_marker(ev, net, lane_id) if args.markers else None
    print("t=%6.1f  %-9s  cạnh=%s  làn=%d  kéo dài %.0f giây  %s" % (
        now, ev["kind"], edge_id, lane_index, ev["duration"], note))

    def restore():
        if undo is not None:
            undo()
        if marker is not None:
            traci.poi.remove(marker)

    return restore


def read_metrics(tripinfo_path, summary_path):
    durations, waits, losses = [], [], []
    for _, el in ET.iterparse(tripinfo_path):
        if el.tag != "tripinfo":
            continue
        if not el.get("id").startswith("obstacle_"):
            durations.append(float(el.get("duration")))
            waits.append(float(el.get("waitingTime")))
            losses.append(float(el.get("timeLoss")))
        el.clear()

    speeds = []
    last = {}
    for _, el in ET.iterparse(summary_path):
        if el.tag != "step":
            continue
        speed = float(el.get("meanSpeed"))
        if speed >= 0:
            speeds.append(speed)
        last = dict(el.attrib)
        el.clear()

    def mean(values):
        return statistics.fmean(values) if values else float("nan")

    return {
        "arrived": len(durations),
        "waiting_end": int(last.get("waiting", 0)),
        "mean_duration": mean(durations),
        "mean_waiting": mean(waits),
        "mean_time_loss": mean(losses),
        "mean_speed": mean(speeds),
        "teleports": int(last.get("teleports", 0)),
        "collisions": int(last.get("collisions", 0)),
        "dropped": max(
            0,
            int(last.get("loaded", 0)) - int(last.get("inserted", 0)) - int(last.get("waiting", 0)),
        ),
    }


def run_once(args, cfg_path, net, ids, weights, kinds, seed, config_name, with_events):
    tag = "%s_seed%d" % (config_name, seed)
    run_dir = os.path.join(args.out_dir, tag)
    os.makedirs(run_dir, exist_ok=True)
    tripinfo_path = os.path.join(run_dir, "tripinfo.xml")
    summary_path = os.path.join(run_dir, "summary.xml")

    events = []
    if with_events:
        events = sample_events(random.Random(seed), net, ids, weights, args, kinds)
        events_path = os.path.join(run_dir, "events.csv")
        write_events(events_path, events)
        print("Danh sách sự cố: %s" % events_path)

    binary = sumolib.checkBinary("sumo-gui" if args.gui else "sumo")
    cmd = [
        binary,
        "-c", cfg_path,
        "--end", str(args.end),
        "--seed", str(seed),
        "--scale", str(args.scale),
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--ignore-route-errors", "true",
        "--tripinfo-output", tripinfo_path,
        "--summary-output", summary_path,
    ]
    if args.reroute:
        cmd += ["--device.rerouting.probability", "1", "--device.rerouting.period", "60"]
    if args.gui:
        cmd += ["--start", "true", "--quit-on-end", "true"]

    traci.start(cmd)
    pending = list(events)
    active = []
    try:
        if events:
            traci.vehicletype.copy("DEFAULT_VEHTYPE", "obstacle_base")
            traci.vehicletype.setLength("obstacle_base", 4.5)
            traci.vehicletype.setWidth("obstacle_base", 1.8)
            traci.vehicletype.setMinGap("obstacle_base", 0.5)

        while traci.simulation.getTime() < args.end and traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            now = traci.simulation.getTime()
            while pending and pending[0]["start"] <= now:
                ev = pending.pop(0)
                restore = activate(ev, now, net, args)
                active.append((ev["end_time"], restore))
            still_active = []
            for end_time, restore in active:
                if end_time <= now:
                    restore()
                else:
                    still_active.append((end_time, restore))
            active = still_active
    finally:
        traci.close()

    row = read_metrics(tripinfo_path, summary_path)
    row.update({"config": config_name, "seed": seed, "events": len(events)})
    return row


def summarize(rows):
    by_config = {}
    for row in rows:
        by_config.setdefault(row["config"], []).append(row)

    base = by_config.get("baseline")
    print("\n=== TỔNG HỢP (trung bình qua các seed; trong ngoặc là độ lệch chuẩn) ===")
    header = "%-12s %-5s " % ("config", "n") + " ".join("%-20s" % m for m in METRICS)
    print(header)
    for name, group in by_config.items():
        cells = []
        for m in METRICS:
            values = [r[m] for r in group]
            avg = statistics.fmean(values)
            sd = statistics.pstdev(values) if len(values) > 1 else 0.0
            text = "%.2f (%.2f)" % (avg, sd)
            if base is not None and name != "baseline":
                base_avg = statistics.fmean([r[m] for r in base])
                if base_avg:
                    text += " %+.0f%%" % (100.0 * (avg - base_avg) / abs(base_avg))
            cells.append("%-20s" % text)
        print("%-12s %-5d " % (name, len(group)) + " ".join(cells))


def main():
    p = argparse.ArgumentParser(description="Mô phỏng Quận 1 với sự cố ngẫu nhiên")
    p.add_argument("--cfg", default=os.path.join(BASE_DIR, "simulation.sumocfg"))
    p.add_argument("--out-dir", default=os.path.join(BASE_DIR, "results_uncertainty"))
    p.add_argument("--end", type=float, default=1800.0, help="thời điểm kết thúc (giây)")
    p.add_argument("--scale", type=float, default=0.05,
                   help="hệ số tải; 1.0 là tải gốc đã hiệu chuẩn nhưng mạng bị kẹt cứng")
    p.add_argument("--seeds", type=int, nargs="+", default=[1])
    p.add_argument("--baseline", action="store_true", help="chạy thêm kịch bản không sự cố")
    p.add_argument("--events", type=int, default=5, help="số sự cố mỗi lần chạy (0 là bỏ qua)")
    p.add_argument("--kind", choices=KINDS + ["mixed"], default="mixed")
    p.add_argument("--block", choices=["partial", "full"], default="full")
    p.add_argument("--duration-min", type=float, default=120.0)
    p.add_argument("--duration-max", type=float, default=600.0)
    p.add_argument("--event-start-min", type=float, default=300.0,
                   help="không đặt sự cố trước mốc này (để mạng có thời gian đầy xe)")
    p.add_argument("--event-start-margin", type=float, default=300.0,
                   help="không đặt sự cố trong khoảng này trước khi kết thúc")
    p.add_argument("--min-edge-length", type=float, default=40.0)
    p.add_argument("--weighting", choices=["traffic", "uniform"], default="traffic")
    p.add_argument("--slow-min", type=float, default=1.5, help="tốc độ giảm tối thiểu (m/s)")
    p.add_argument("--slow-max", type=float, default=4.0, help="tốc độ giảm tối đa (m/s)")
    p.add_argument("--reroute", action="store_true",
                   help="bật tự đổi đường; nên dùng cho cả baseline để so sánh công bằng")
    p.add_argument("--gui", action="store_true")
    p.add_argument("--markers", action="store_true",
                   help="vẽ chấm màu tại vị trí sự cố (tự bật khi có --gui)")
    args = p.parse_args()
    args.markers = args.markers or args.gui

    if not args.baseline and args.events <= 0:
        p.error("cần --baseline hoặc --events lớn hơn 0")

    cfg_path = os.path.abspath(args.cfg)
    net_file, route_files = read_cfg_paths(cfg_path)
    net = sumolib.net.readNet(net_file)
    usage = edge_usage(route_files)
    ids, weights = build_candidates(net, usage, args.min_edge_length, args.weighting)
    if not ids:
        sys.exit("Không tìm thấy cạnh phù hợp để đặt sự cố")
    print("Số cạnh ứng viên đặt sự cố: %d" % len(ids))

    kinds = KINDS if args.kind == "mixed" else [args.kind]
    configs = []
    if args.baseline:
        configs.append(("baseline", False))
    if args.events > 0:
        configs.append((args.kind, True))

    os.makedirs(args.out_dir, exist_ok=True)
    rows = []
    for seed in args.seeds:
        for name, with_events in configs:
            print("Chạy %s, seed %d" % (name, seed))
            rows.append(run_once(args, cfg_path, net, ids, weights, kinds, seed, name, with_events))

    results_path = os.path.join(args.out_dir, "results.csv")
    fields = ["config", "seed", "events"] + METRICS
    new_file = not os.path.exists(results_path)
    with open(results_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)

    summarize(rows)
    print("\nKết quả chi tiết: %s" % results_path)


if __name__ == "__main__":
    main()
