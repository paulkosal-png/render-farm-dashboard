"""Render a self-contained HTML dashboard (no external CSS or JS)."""

from __future__ import annotations

import html

from farmdash.analyze import SEVERITY_NAMES

CSS = """
:root {
  --bg: #0f1419;
  --panel: #172027;
  --line: #2a3844;
  --text: #e7eef3;
  --muted: #8aa0b0;
  --ok: #3dbf7a;
  --info: #6f8ea3;
  --warning: #e2b344;
  --serious: #e07a48;
  --critical: #e04b4b;
  --accent: #4db8d4;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.45 "Segoe UI", system-ui, sans-serif; }
header { padding: 28px 28px 8px; }
h1 { margin: 0 4px 4px 0; font-size: 22px; font-weight: 650; letter-spacing: -0.02em; }
.lede { color: var(--muted); margin: 0; }
.note { margin: 8px 28px 0; color: var(--muted); font-size: 13px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px; padding: 20px 28px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }
.tile .lbl { color: var(--muted); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; }
.tile .val { font-size: 28px; font-weight: 650; margin-top: 4px; font-variant-numeric: tabular-nums; }
.tile .hint { color: var(--muted); font-size: 12px; margin-top: 2px; }
.controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 4px 28px 16px; }
.controls input, .controls select { font: inherit; background: var(--panel); color: var(--text);
  border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px; }
.controls label { color: var(--muted); font-size: 13px; display: flex; gap: 6px; align-items: center; }
h2 { font-size: 16px; margin: 8px 28px 8px; }
h2 span { color: var(--muted); font-weight: 500; font-size: 13px; }
table { width: calc(100% - 56px); margin: 0 28px 32px; border-collapse: collapse; font-size: 13px; }
th { text-align: left; color: var(--muted); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
  border-bottom: 1px solid var(--line); padding: 8px 8px; }
td { border-bottom: 1px solid var(--line); padding: 8px; vertical-align: top; }
tr.node { cursor: pointer; }
tr.node:hover td, tr.job:hover td { background: #1c2a33; }
tr.detail td { background: #1c2a33; padding: 12px 16px 16px; }
tr.detail[hidden], tr.node[hidden], tr.job[hidden] { display: none; }
.badge { display: inline-flex; align-items: center; gap: 6px; font-weight: 650; text-transform: capitalize; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
.ok .dot { background: var(--ok); } .info .dot { background: var(--info); }
.warning .dot { background: var(--warning); } .serious .dot { background: var(--serious); }
.critical .dot { background: var(--critical); }
.flags { margin: 0; padding-left: 18px; }
.muted { color: var(--muted); }
.filter-status { padding: 0 28px 8px; color: var(--muted); font-size: 13px; min-height: 1.2em; }
.filter-status a { color: var(--accent); }
"""

JS = """
const nodes = [...document.querySelectorAll('tr.node')];
const jobs = [...document.querySelectorAll('tr.job')];
const q = document.getElementById('q');
const attention = document.getElementById('attention');
const group = document.getElementById('group');
const status = document.getElementById('filter-status');

function apply() {
  const text = q.value.trim().toLowerCase();
  let shown = 0;
  for (const row of nodes) {
    const matchText = !text || row.dataset.search.includes(text);
    const matchAtt = !attention.checked || Number(row.dataset.sev) >= 2;
    const matchGroup = !group.value || row.dataset.groups.split(',').includes(group.value);
    const show = matchText && matchAtt && matchGroup;
    row.hidden = !show;
    const detail = row.nextElementSibling;
    if (!show) detail.hidden = true;
    if (show) shown += 1;
  }
  if (!text && !attention.checked && !group.value) {
    status.textContent = '';
  } else {
    status.innerHTML = 'Showing ' + shown + ' of ' + nodes.length + ' workers. <a href="#" id="clear">Clear filters</a>';
    document.getElementById('clear').addEventListener('click', (ev) => {
      ev.preventDefault();
      q.value = ''; attention.checked = false; group.value = ''; apply();
    });
  }
}

q.addEventListener('input', apply);
attention.addEventListener('change', apply);
group.addEventListener('change', apply);
document.querySelectorAll('tr.node').forEach((row) => {
  row.addEventListener('click', () => {
    const detail = row.nextElementSibling;
    detail.hidden = !detail.hidden;
  });
});
"""


def _esc(value) -> str:
    return html.escape("" if value is None else str(value))


def _badge(severity: int, label: str | None = None) -> str:
    name = SEVERITY_NAMES.get(severity, "ok")
    text = _esc(label or name)
    return f'<span class="badge {name}"><span class="dot"></span>{text}</span>'


def _search_blob(node: dict) -> str:
    parts = [node["name"], node["state"], *node.get("groups", []), *node.get("pools", [])]
    parts.extend(flag["text"] for flag in node.get("flags") or [])
    parts.extend(node.get("drivers") or [])
    return " ".join(parts).lower()


def render(nodes: list, jobs: list, summary: dict, meta: dict, standards: dict) -> str:
    groups = sorted({g for node in nodes for g in node.get("groups") or []})
    group_opts = "".join(f'<option value="{_esc(g)}">{_esc(g)}</option>' for g in groups)
    driver = (standards or {}).get("driver") or "n/a"
    plugin_bits = (
        ", ".join(
            f"{name} {ver}"
            for name, ver in sorted(((standards or {}).get("plugins") or {}).items())
        )
        or "n/a"
    )
    tiles = [
        (
            "Workers",
            summary["nodes"],
            ", ".join(f"{k} {v}" for k, v in (summary.get("states") or {}).items()),
        ),
        ("Needs attention", summary["attention"], f"{summary['critical']} critical"),
        ("Errors", summary["errors"], f"last {int(summary.get('error_window_hours') or 24)}h"),
        ("Jobs", summary["jobs_total"], f"{summary['jobs_active']} active"),
    ]
    tile_html = "".join(
        f'<div class="tile"><div class="lbl">{_esc(lbl)}</div><div class="val">{_esc(val)}</div>'
        f'<div class="hint">{_esc(hint)}</div></div>'
        for lbl, val, hint in tiles
    )

    body_rows = []
    for node in nodes:
        flags = node.get("flags") or []
        flag_txt = "; ".join(f["text"] for f in flags) or "All clear"
        plugins = (
            ", ".join(
                f"{p.get('plugin_name')} {p.get('plugin_version')}"
                for p in node.get("plugins") or []
            )
            or "—"
        )
        drivers = ", ".join(node.get("drivers") or []) or "—"
        gpus = (
            ", ".join(f"{g.get('model')} ({g.get('vram_mb')} MB)" for g in node.get("gpus") or [])
            or "—"
        )
        err_rows = (
            "".join(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (
                    _esc(e.get("time")),
                    _esc(e.get("category")),
                    _esc(e.get("job")),
                    _esc(e.get("message")),
                )
                for e in node.get("errors_recent") or []
            )
            or "<tr><td colspan='4' class='muted'>No recent errors.</td></tr>"
        )
        flag_list = (
            "".join(f"<li>{_esc(f['text'])}</li>" for f in flags) or "<li class='muted'>None</li>"
        )
        body_rows.append(
            f"""<tr class="node {SEVERITY_NAMES[node["severity"]]}" data-sev="{node["severity"]}"
              data-groups="{_esc(",".join(node.get("groups") or []))}"
              data-search="{_esc(_search_blob(node))}">
              <td>{_badge(node["severity"])}</td>
              <td>{_esc(node["name"])}</td>
              <td>{_esc(node["state"])}</td>
              <td>{_esc(", ".join(node.get("groups") or []) or "—")}</td>
              <td>{_esc(", ".join(node.get("pools") or []) or "—")}</td>
              <td>{_esc(drivers)}</td>
              <td>{_esc(plugins)}</td>
              <td>{_esc(flag_txt)}</td>
            </tr>
            <tr class="detail" hidden><td colspan="8">
              <ul class="flags">{flag_list}</ul>
              <div class="muted">GPU: {_esc(gpus)} · Last inventory scan: {_esc(node.get("last_scan") or "n/a")}</div>
              <table><thead><tr><th>Time</th><th>Category</th><th>Job</th><th>Message</th></tr></thead>
              <tbody>{err_rows}</tbody></table>
            </td></tr>"""
        )

    job_rows = []
    for job in jobs:
        job_rows.append(
            f"""<tr class="job {SEVERITY_NAMES[job["severity"]]}">
              <td>{_badge(job["severity"])}</td>
              <td>{_esc(job["name"])}</td>
              <td>{_esc(job.get("status"))}</td>
              <td>{_esc(job.get("user"))}</td>
              <td>{_esc(job.get("renderer") or job.get("plugin"))} {_esc(job.get("renderer_version") or job.get("plugin_version"))}</td>
              <td>{_esc(job.get("group"))} / {_esc(job.get("pool"))}</td>
              <td>{job["ready"]} / {job["candidates"]}</td>
              <td>{_esc(job.get("issue") or "—")}</td>
            </tr>"""
        )

    generated = _esc(meta.get("generated") or "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Render farm dashboard</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Render farm dashboard</h1>
  <p class="lede">Read-only view of queue state, inventory, and plugin versions. Generated {generated}.</p>
</header>
<p class="note">All names, jobs, and hardware in this page come from the bundled synthetic fixture. Farm standard: driver {_esc(driver)}; plugins {_esc(plugin_bits)}.</p>
<div class="tiles">{tile_html}</div>
<div class="controls">
  <input type="search" id="q" placeholder="Filter workers">
  <label><input type="checkbox" id="attention"> Needs attention</label>
  <label>Group <select id="group"><option value="">All</option>{group_opts}</select></label>
</div>
<div class="filter-status" id="filter-status"></div>
<h2>Workers <span>click a row for errors and inventory detail</span></h2>
<table>
  <thead><tr><th>Status</th><th>Name</th><th>State</th><th>Groups</th><th>Pools</th><th>Driver</th><th>Plugins</th><th>Flags</th></tr></thead>
  <tbody>
    {"".join(body_rows)}
  </tbody>
</table>
<h2>Jobs <span>ready / candidates</span></h2>
<table>
  <thead><tr><th>Status</th><th>Name</th><th>State</th><th>User</th><th>Renderer</th><th>Group / pool</th><th>Ready</th><th>Issue</th></tr></thead>
  <tbody>
    {"".join(job_rows)}
  </tbody>
</table>
<script>{JS}</script>
</body>
</html>
"""
