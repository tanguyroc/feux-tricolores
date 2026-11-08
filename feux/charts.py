"""Graphiques SVG autonomes (sans bibliothèque) pour les rapports : courbes multi-séries avec échelle log,
légende, étiquettes directes, grille discrète et survol (croix + infobulle)."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

# Palette catégorielle validée (dataviz, mode clair) : bleu, orange, aqua.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"]


def _ticks_log(vmin: float, vmax: float) -> list[float]:
    lo, hi = math.floor(math.log10(vmin)), math.ceil(math.log10(vmax))
    ticks = []
    for e in range(lo, hi + 1):
        for m in (1, 2, 5):
            v = m * 10 ** e
            if vmin <= v <= vmax:
                ticks.append(v)
    return ticks


def line_chart(series: dict[str, pd.Series], title: str, subtitle: str = "", log: bool = True,
               width: int = 960, height: int = 420, y_format: str = "x", chart_id: str = "c1") -> str:
    """`series` : nom -> série indexée par date (alignées ou non). Retourne un bloc HTML (svg + légende + script)."""
    df = pd.concat(series, axis=1).dropna(how="all").ffill()
    df = df.resample("W-FRI").last().dropna()
    names = list(df.columns)
    ml, mr, mt, mb = 56, 150, 36, 40
    pw, ph = width - ml - mr, height - mt - mb
    x0, x1 = df.index[0].value, df.index[-1].value
    vals = df.to_numpy()
    vmin, vmax = np.nanmin(vals), np.nanmax(vals)
    if log:
        vmin = max(vmin, 1e-6)
        fy = lambda v: mt + ph - (math.log10(v) - math.log10(vmin)) / (math.log10(vmax) - math.log10(vmin)) * ph
        yticks = _ticks_log(vmin, vmax)
    else:
        span = vmax - vmin or 1.0
        fy = lambda v: mt + ph - (v - vmin) / span * ph
        yticks = list(np.linspace(vmin, vmax, 6))
    fx = lambda t: ml + (t - x0) / (x1 - x0) * pw
    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' xmlns='http://www.w3.org/2000/svg' id='{chart_id}' style='font-family:system-ui,sans-serif;font-size:12px;max-width:{width}px;display:block'>"]
    parts.append(f"<text x='{ml}' y='16' font-size='15' font-weight='600' fill='#0b0b0b'>{title}</text>")
    if subtitle:
        parts.append(f"<text x='{ml}' y='31' font-size='12' fill='#52514e'>{subtitle}</text>")
    # grille horizontale
    for v in yticks:
        y = fy(v)
        label = (f"{v:g}{y_format}" if y_format == "x" else f"{100 * v:.0f} %")
        parts.append(f"<line x1='{ml}' x2='{ml + pw}' y1='{y:.1f}' y2='{y:.1f}' stroke='#e6e8eb' stroke-width='1'/>")
        parts.append(f"<text x='{ml - 6}' y='{y + 4:.1f}' text-anchor='end' fill='#52514e'>{label}</text>")
    # années
    years = pd.date_range(df.index[0].normalize(), df.index[-1], freq="YS")
    step = max(1, int(math.ceil(len(years) / 12)))
    for yr in years[::step]:
        x = fx(yr.value)
        parts.append(f"<line x1='{x:.1f}' x2='{x:.1f}' y1='{mt + ph}' y2='{mt + ph + 4}' stroke='#9a9a9a'/>")
        parts.append(f"<text x='{x:.1f}' y='{mt + ph + 18}' text-anchor='middle' fill='#52514e'>{yr.year}</text>")
    parts.append(f"<line x1='{ml}' x2='{ml + pw}' y1='{mt + ph}' y2='{mt + ph}' stroke='#9a9a9a'/>")
    # courbes
    for i, name in enumerate(names):
        col = SERIES_COLORS[i % len(SERIES_COLORS)]
        pts = " ".join(f"{fx(t.value):.1f},{fy(v):.1f}" for t, v in df[name].items() if v == v and v > 0)
        parts.append(f"<polyline fill='none' stroke='{col}' stroke-width='2' stroke-linejoin='round' points='{pts}'/>")
        last_v = df[name].iloc[-1]
        parts.append(f"<circle cx='{fx(df.index[-1].value):.1f}' cy='{fy(last_v):.1f}' r='4' fill='{col}' stroke='#fff' stroke-width='2'/>")
        parts.append(f"<text x='{ml + pw + 8}' y='{fy(last_v) + 4:.1f}' fill='#0b0b0b'>{name} · {last_v:,.0f}{y_format if y_format == 'x' else ''}</text>")
    # calque de survol
    parts.append(f"<line id='{chart_id}-cross' x1='0' x2='0' y1='{mt}' y2='{mt + ph}' stroke='#52514e' stroke-dasharray='3,3' visibility='hidden'/>")
    parts.append(f"<rect id='{chart_id}-hit' x='{ml}' y='{mt}' width='{pw}' height='{ph}' fill='transparent'/>")
    parts.append("</svg>")
    legend = "".join(f"<span style='display:inline-flex;align-items:center;gap:6px;margin-right:16px'><i style='display:inline-block;width:14px;height:3px;background:{SERIES_COLORS[i % len(SERIES_COLORS)]}'></i>{n}</span>" for i, n in enumerate(names))
    data = {"x": [int(t.value // 10 ** 6) for t in df.index], "s": {n: [None if not (v == v) else round(float(v), 4) for v in df[n]] for n in names},
            "ml": ml, "pw": pw, "x0": x0 // 10 ** 6, "x1": x1 // 10 ** 6, "fmt": y_format}
    script = f"""<div id='{chart_id}-tip' style='position:absolute;display:none;background:#fff;border:1px solid #e6e8eb;border-radius:6px;padding:6px 8px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);pointer-events:none'></div>
<script>(function(){{var d={json.dumps(data)};var svg=document.getElementById('{chart_id}');var hit=document.getElementById('{chart_id}-hit');var cross=document.getElementById('{chart_id}-cross');var tip=document.getElementById('{chart_id}-tip');
hit.addEventListener('mousemove',function(e){{var r=svg.getBoundingClientRect();var sx=svg.viewBox.baseVal.width/r.width;var px=(e.clientX-r.left)*sx;var t=d.x0+(px-d.ml)/d.pw*(d.x1-d.x0);var i=0,lo=0,hi=d.x.length-1;while(lo<hi){{var m=(lo+hi)>>1;if(d.x[m]<t)lo=m+1;else hi=m;}}i=lo;var X=d.ml+(d.x[i]-d.x0)/(d.x1-d.x0)*d.pw;cross.setAttribute('x1',X);cross.setAttribute('x2',X);cross.setAttribute('visibility','visible');
var dt=new Date(d.x[i]).toLocaleDateString('fr-FR');var html='<b>'+dt+'</b>';for(var k in d.s){{var v=d.s[k][i];html+='<br>'+k+' : '+(v==null?'–':(d.fmt=='x'?v.toLocaleString('fr-FR',{{maximumFractionDigits:1}})+'x':(100*v).toFixed(0)+' %'));}}
tip.innerHTML=html;tip.style.display='block';tip.style.left=(e.pageX+14)+'px';tip.style.top=(e.pageY-10)+'px';}});
hit.addEventListener('mouseleave',function(){{cross.setAttribute('visibility','hidden');tip.style.display='none';}});}})();</script>"""
    return f"<div style='position:relative'>{''.join(parts)}<div style='font-size:12px;color:#52514e;margin:4px 0 12px'>{legend}</div>{script}</div>"
