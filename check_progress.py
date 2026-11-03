from pathlib import Path

sweep_dir = Path("sumo_scenarios/lambda_sensitivity_sweep")
for f in sorted(sweep_dir.glob("tripinfo_lambda_*.xml")):
    try:
        with open(f, "rb") as fp:
            fp.seek(0, 2)
            size = fp.tell()
            fp.seek(max(0, size - 4000), 0)
            tail = fp.read().decode("utf-8", errors="ignore")
        departs = []
        for line in tail.splitlines():
            if 'depart="' in line:
                try:
                    d = float(line.split('depart="')[1].split('"')[0])
                    departs.append(d)
                except Exception:
                    pass
        if departs:
            print(f"{f.name:25s} | size: {size:10,d} bytes | latest depart: {max(departs):6.1f}s / 8100s ({max(departs)/8100*100:4.1f}%)")
        else:
            print(f"{f.name:25s} | size: {size:10,d} bytes | starting...")
    except Exception as e:
        print(f"{f.name:25s} | error: {e}")
