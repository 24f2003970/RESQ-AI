"""Render saved Part 12 reliability bins with explicit dev/test scopes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "backend" / "ml_artifacts" / "reliability_evaluation.json"
OUTPUT = ROOT / "docs" / "evidence" / "part15" / "calibration_reliability.svg"


def plot() -> Path:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    calibration = report["calibration"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1120, 540
    panels = [
        ("development_nested_outer_raw", "development_nested_outer_calibrated", "Development · nested grouped adoption"),
        ("final_held_out_raw", "final_held_out_platt", "Untouched synthetic test · descriptive only"),
    ]
    fragments = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                 '<rect width="100%" height="100%" fill="#f8fafc"/>',
                 '<text x="560" y="30" text-anchor="middle" font-family="Arial,sans-serif" font-size="20" font-weight="700" fill="#0f172a">RESQ-AI synthetic future-exposure reliability</text>']
    series = [("#64748b", "Raw random forest"), ("#06b6d4", "Platt calibrated")]
    for panel_index, (raw_key, cal_key, title) in enumerate(panels):
        left, top, plot_w, plot_h = 90 + panel_index * 520, 80, 410, 350
        xmap = lambda value: left + value * plot_w
        ymap = lambda value: top + (1 - value) * plot_h
        fragments.append(f'<text x="{left + plot_w/2}" y="58" text-anchor="middle" font-family="Arial,sans-serif" font-size="14" font-weight="700" fill="#0f172a">{title}</text>')
        for tick in range(6):
            value = tick / 5
            x, y = xmap(value), ymap(value)
            fragments.append(f'<path d="M {x:.2f} {top} V {top+plot_h} M {left} {y:.2f} H {left+plot_w}" stroke="#dbe4ee" stroke-width="1"/>')
            fragments.append(f'<text x="{x:.2f}" y="{top+plot_h+19}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#475569">{value:.1f}</text>')
            fragments.append(f'<text x="{left-10}" y="{y+4:.2f}" text-anchor="end" font-family="Arial,sans-serif" font-size="10" fill="#475569">{value:.1f}</text>')
        fragments.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#64748b"/>')
        fragments.append(f'<path d="M {left} {top+plot_h} L {left+plot_w} {top}" stroke="#94a3b8" stroke-dasharray="6 5" stroke-width="1.5"/>')
        for key, (color, label) in zip((raw_key, cal_key), series):
            points = calibration[key]["reliability_diagram"]
            coords = [(xmap(row["mean_score"]), ymap(row["observed_frequency"])) for row in points]
            path = " ".join(("M" if index == 0 else "L") + f" {x:.2f} {y:.2f}" for index, (x, y) in enumerate(coords))
            fragments.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.3"/>')
            for (x, y), row in zip(coords, points):
                radius = min(5.0, 2.2 + (row["count"] ** 0.5) / 55)
                fragments.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" stroke="white" stroke-width="1"><title>{label}: n={row["count"]}, mean predicted={row["mean_score"]:.3f}, observed={row["observed_frequency"]:.3f}</title></circle>')
        fragments.append(f'<text x="{left+plot_w/2}" y="{top+plot_h+43}" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" fill="#334155">Mean predicted probability</text>')
        fragments.append(f'<text x="{left-56}" y="{top+plot_h/2}" transform="rotate(-90 {left-56} {top+plot_h/2})" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" fill="#334155">Observed positive frequency</text>')
        legend_x, legend_y = left+13, top+16
        for idx, (color, label) in enumerate(series):
            yy = legend_y + idx * 21
            fragments.append(f'<path d="M {legend_x} {yy} h 20" stroke="{color}" stroke-width="3"/><text x="{legend_x+27}" y="{yy+4}" font-family="Arial,sans-serif" font-size="10" fill="#334155">{label}</text>')
        fragments.append(f'<text x="{left+plot_w-6}" y="{top+19}" text-anchor="end" font-family="Arial,sans-serif" font-size="9" fill="#64748b">Dashed line: perfect calibration</text>')
    fragments.append('<text x="560" y="520" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#475569">Ten fixed-width bins · development adoption uses nested scenario-group folds · final test split did not choose calibration</text>')
    fragments.append('</svg>')
    OUTPUT.write_text("\n".join(fragments) + "\n", encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(plot())
