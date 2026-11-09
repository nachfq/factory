#!/usr/bin/env python3
"""Generate an importable native Netdata resource dashboard for this host."""
import argparse
import copy
import json
from pathlib import Path
import urllib.request
import uuid


def build_dashboard(template, snapshot, charts):
    dashboard = {"name": "Recursos", "respectNodesScope": True, "cards": {},
                 "layout": {"A": []}, "containerIds": ["A"],
                 "containers": {"A": {"name": "Recursos"}}}
    host = snapshot.get("hostname", "Host")
    groups = [[(f"{host} · CPU", "system.cpu", [], "selected", "line"),
               (f"{host} · RAM", "system.ram", ["used"], "dimension", "area"),
               (f"{host} · Disco", "statsd_factory.host_disk_space", [], "dimension", "stacked")]]
    for item in snapshot["instances"]:
        name = item["name"]
        groups.append([
            (f"{name} · CPU (100% = 1 núcleo)", f"cgroup_{name}.cpu", [], "selected", "line"),
            (f"{name} · RAM", f"cgroup_{name}.mem_usage", ["ram"], "dimension", "area"),
            (f"{name} · Disco", f"statsd_factory.incus.{name}.used_gauge", [], "dimension", "line")])
    for row, group in enumerate(groups):
        for column, (title, chart_id, dimensions, group_by, chart_type) in enumerate(group):
            if chart_id not in charts:
                raise ValueError(f"Chart not collected yet: {chart_id}; run storage collection first")
            context = charts[chart_id]["context"]
            card = copy.deepcopy(template)
            card_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "factory-netdata:"+chart_id))
            card.update(id=card_id, contextScope=[context], title=title, customTitle=title,
                        selectedDimensions=dimensions, selectedInstances=[chart_id],
                        groupBy=[group_by], aggregationMethod="sum", chartType=chart_type,
                        nodesScope=[], selectedNodes=[], selectedLabels=[], nodeFilters={})
            dashboard["cards"][card_id] = card
            # Native dashboard grids have 12 tracks; three cards must use four
            # each. Default single-card width 10 would overflow a three-card row.
            dashboard["layout"]["A"].append(dict(id=card_id, left=column*4, top=row*10,
                width=4, height=9, minWidth=1, minHeight=1, moved=False))
    return dashboard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:19999")
    parser.add_argument("--output", type=Path, default=Path("Recursos.json"))
    args = parser.parse_args()
    def get(path):
        with urllib.request.urlopen(args.url.rstrip("/")+path, timeout=15) as response:
            return json.load(response)
    template = json.loads(Path(__file__).with_name("native-card-template.json").read_text())
    dashboard = build_dashboard(template, get("/factory/incus-storage.json"), get("/api/v1/charts")["charts"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False)+"\n")
    print(f"Created {args.output}: {len(dashboard['cards'])} native charts")


if __name__ == "__main__":
    main()
