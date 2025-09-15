#!/usr/bin/env python3
"""
generate_spread_charts_html.py

Scan a directory for futures monthly CSVs, pair adjacent month contracts,
compute spreads, generate charts (stretched to window), embed them as
base64 in a single HTML, and show spread values below each chart (no year in dates).

Usage:
    python generate_spread_charts_html.py --dir ./csvs --out spreads.html

Requirements:
    pip install pandas matplotlib
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re, base64, io, argparse
from datetime import datetime
import html

# Futures month codes
MONTH_CODES = {'F':1,'G':2,'H':3,'J':4,'K':5,'M':6,'N':7,'Q':8,'U':9,'V':10,'X':11,'Z':12}
FNAME_RE = re.compile(r'^(?P<root>.+?)(?P<month>[FGHJKMNQUVXZ])(?P<year>\d{2,4})?$', re.IGNORECASE)

def parse_filename(fname):
    m = FNAME_RE.match(fname)
    if not m: return None
    root = m.group('root')
    month = m.group('month').upper()
    y = m.group('year')
    year = None
    if y:
        year = int(y) if len(y)==4 else 2000+int(y)
    return root, month, year

def scan_csvs(directory: Path):
    parsed = {}
    for f in directory.glob("*.csv"):
        p = parse_filename(f.stem)
        if not p: continue
        root, month, year = p
        parsed.setdefault(root, []).append({"path": f, "month": month, "year": year})
    return parsed

def sort_entries(entries):
    return sorted(entries, key=lambda e: ((e["year"] if e["year"] else 9999), MONTH_CODES[e["month"]]))

def read_series(path: Path, date_col="Date", price_col="Close"):
    df = pd.read_csv(path, parse_dates=[date_col])
    df = df[[date_col, price_col]].dropna()
    df = df.rename(columns={date_col:"Date", price_col:"Price"})
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.sort_values("Date").drop_duplicates("Date")
    df = df.set_index("Date")
    return df

def make_chart_base64(a_path, b_path, date_col="Date", price_col="Close"):
    a = read_series(a_path, date_col, price_col)
    b = read_series(b_path, date_col, price_col)
    common = a.join(b, how="inner", lsuffix="_A", rsuffix="_B")
    if common.empty: return None
    common["Spread"] = common["Price_A"] - common["Price_B"]
    dates_noyear = [d.strftime("%b %d") for d in common.index]

    # Plot
    plt.figure(figsize=(12,6))
    plt.plot(dates_noyear, common["Price_A"], label=a_path.stem)
    plt.plot(dates_noyear, common["Price_B"], label=b_path.stem)
    plt.plot(dates_noyear, common["Spread"], label="Spread (A-B)", linestyle="--")
    plt.title(f"Spread: {a_path.stem} - {b_path.stem}")
    plt.xlabel("Date")
    plt.ylabel("Price / Spread")
    plt.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150)
    plt.close()
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    rows_html = "".join(f"<div>{d}: Spread = {s}</div>" for d,s in zip(dates_noyear, common["Spread"]))
    return {"title": f"{a_path.stem} - {b_path.stem}", "img": img_b64, "rows_html": rows_html}

def generate_html(results, out_html: Path):
    parts = []
    parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    parts.append(f"<title>2-Month Spreads</title>")
    parts.append("<style>"
                 "body{font-family:Arial;margin:0;padding:0;}"
                 ".chart{width:100vw;text-align:center;margin-bottom:20px;}"
                 "img{width:100%;height:auto;display:block;}"
                 ".spreads{text-align:center;font-size:14px;margin-bottom:40px;}"
                 "</style></head><body>")
    parts.append(f"<h1 style='text-align:center;'>2-Month Spread Charts</h1>")
    parts.append(f"<p style='text-align:center;font-size:12px;'>Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>")
    for r in results:
        parts.append("<div class='chart'>")
        parts.append(f"<h2>{html.escape(r['title'])}</h2>")
        parts.append(f"<img src='data:image/png;base64,{r['img']}' alt='{html.escape(r['title'])}'>")
        parts.append(f"<div class='spreads'>{r['rows_html']}</div>")
        parts.append("</div>")
    parts.append("</body></html>")
    out_html.write_text("\n".join(parts), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir","-d", default=".", help="Directory with CSVs")
    parser.add_argument("--out","-o", default="spreads.html", help="Output HTML")
    args = parser.parse_args()

    basedir = Path(args.dir)
    parsed = scan_csvs(basedir)
    results = []

    for root, entries in parsed.items():
        entries = sort_entries(entries)
        for i in range(len(entries)-1):
            a = entries[i]["path"]
            b = entries[i+1]["path"]
            try:
                r = make_chart_base64(a, b)
                if r: results.append(r)
            except Exception as e:
                print(f"Error processing {a} / {b}: {e}")

    out_html = basedir / args.out
    generate_html(results, out_html)
    print(f"Done. HTML written to {out_html}")

if __name__=="__main__":
    main()
