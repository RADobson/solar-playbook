"""Standalone, dependency-free report; escapes every external string."""
from html import escape


def render(report: dict) -> str:
    selected = report.get("selected")
    title = escape(report.get("scenario", "Energy plan"))
    content = f'<p class="notice">{escape(report["message"])}</p>'
    if selected:
        metrics = [("EV battery energy added", f'{selected["ev_added_kwh"]:.1f} kWh'),
                   ("Variable energy cost", f'A${selected["energy_cost_aud"]:.2f}'),
                   ("Battery at end", f'{selected["ending_battery_kwh"]:.1f} kWh'),
                   ("DC solar curtailed", f'{selected["curtailed_kwh"]:.1f} kWh')]
        content += '<div class="cards">' + ''.join(f'<div><small>{k}</small><strong>{v}</strong></div>' for k, v in metrics) + '</div>'
        rows = selected["rows"]
        colors = {"pv_dc_kw": "#b97800", "ev_ac_kw": "#006f9b", "grid_import_kw": "#ad3874"}
        peak = max(1, max(row[key] for row in rows for key in colors))
        content += '<h2>One day, three power flows</h2><p>Gold: panel DC power · Blue: EV AC power · Pink: grid import</p>'
        content += '<svg viewBox="0 0 960 265" role="img" aria-label="Power throughout the forecast horizon">'
        for n in range(5):
            y = 225 - 200 * n / 4
            content += f'<path d="M55 {y}H935" stroke="#dce4e4"/><text x="8" y="{y+4}">{peak*n/4:.1f}</text>'
        for key, color in colors.items():
            points = ' '.join(f'{55+i*880/max(1,len(rows)-1):.1f},{225-row[key]/peak*200:.1f}' for i, row in enumerate(rows))
            content += f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>'
        for i in range(0, len(rows), max(1, len(rows)//6)):
            content += f'<text x="{55+i*880/max(1,len(rows)-1):.1f}" y="250">{escape(rows[i]["start"][11:16])}</text>'
        content += '</svg><p class="muted">Power in kW. DC panel output can exceed the AC inverter rating while the battery charges.</p>'
        content += '<h2>Schedules compared</h2><div class="scroll"><table><tr><th>Strategy</th><th>Feasible</th><th>Energy cost</th><th>Ending battery</th><th>Adjusted score</th></tr>'
        for candidate in report["candidates"]:
            mark = ' ✓ selected' if candidate["strategy"] == selected["strategy"] else ''
            content += f'<tr><td>{escape(candidate["strategy"]+mark)}</td><td>{candidate["feasible"]}</td><td>A${candidate["energy_cost_aud"]:.2f}</td><td>{candidate["ending_battery_kwh"]:.1f} kWh</td><td>A${candidate["score_aud"]:.2f}</td></tr>'
        content += '</table></div><p class="muted">Score includes assumed battery wear and the value of ending battery energy. It is not a bill or a savings claim. Supply charges are excluded.</p>'
        content += '<details><summary>Inspect the interval schedule</summary><div class="scroll"><table><tr><th>Time</th><th>EV amps</th><th>Grid kW</th><th>Battery kWh</th></tr>'
        for row in rows:
            content += f'<tr><td>{escape(row["start"])}</td><td>{row["ev_amps"]}</td><td>{row["grid_import_kw"]:.2f}</td><td>{row["battery_after_kwh"]:.2f}</td></tr>'
        content += '</table></div></details>'
    if report.get("advice"):
        advice = report["advice"]
        content += '<h2>Optional explanation</h2><p>' + escape(advice["explanation"]) + '</p>'
        content += '<p class="muted">Source: ' + escape(advice["source"]) + '. Advice does not change the schedule.</p>'
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solar Playbook — {title}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f2f6f5;color:#183330;font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1080px;margin:40px auto;padding:24px}}h1{{font-size:42px;line-height:1.1}}h2{{margin-top:40px}}
.eyebrow{{text-transform:uppercase;letter-spacing:.15em;color:#506e65;font-size:13px}}.notice{{padding:16px;border-left:4px solid #2b7860;background:#e4eeea}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px 0}}.cards div{{padding:20px;background:white;border:1px solid #dbe6e1;border-radius:12px}}
small{{display:block;color:#506e65}}strong{{display:block;font-size:26px;margin-top:10px}}svg{{width:100%;background:white;border-radius:12px}}svg text{{font-size:13px;fill:#506e65}}
table{{border-collapse:collapse;width:100%;background:white}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dce4e4}}th{{font-size:13px}}.scroll{{overflow-x:auto}}.muted,footer{{color:#536963;font-size:14px}}summary{{cursor:pointer}}
@media(max-width:700px){{main{{margin:0;padding:18px}}h1{{font-size:32px}}.cards{{grid-template-columns:1fr 1fr}}strong{{font-size:22px}}}}
</style><main><p class="eyebrow">Solar Playbook · simulation preview</p><h1>Your energy, with a plan.</h1><p>Scenario: <b>{title}</b>. No equipment commands are sent.</p>{content}
<footer><p>Reference model · hypothetical tariffs and equipment · inspect the JSON for full assumptions.<br>Solar Playbook is an independent community project.</p></footer></main></html>'''
