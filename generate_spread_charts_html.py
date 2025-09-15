#!/usr/bin/env python3
"""
Generate 2-month coffee spreads from headerless CSVs.
- Only KC contracts.
- Only coffee month codes: H, K, N, U, Z
- Skip 1-month spreads (take entries[i] + entries[i+2])
- Output PNG charts in coffee_data/charts
- Generate index.html in main directory referencing the PNGs
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import re

COFFEE_MONTH_CODES = {'H':3, 'K':5, 'N':7, 'U':9, 'Z':12}
FNAME_RE = re.compile(r'^(?P<root>.+?)(?P<month>[HKNUZ])(?P<year>\d{2,4})?$', re.IGNORECASE)

def parse_filename(fname):
    m = FNAME_RE.match(fname)
    if not m: return None
    root, month = m.group('root'), m.group('month').upper()
    year = m.group('year')
    if year: year = int(year) if len(year)==4 else 2000+int(year)
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
    return sorted(entries, key=lambda e: ((e["year"] if e["year"] else 9999), COFFEE_MONTH_CODES[e["month"]]))

def read_series(path: Path):
    cols = ["contract","date","open","high","low","close","volume","trades"]
    df = pd.read_csv(path, header=None, names=cols, parse_dates=["date"])
    df = df[["date","close"]].dropna()
    df = df.rename(columns={"date":"Date","close":"Price"})
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.sort_values("Date").drop_duplicates("Date")
    df = df.set_index("Date")
    return df

def make_chart(a_path, b_path, output_dir: Path):
    a = read_series(a_path)
    b = read_series(b_path)
    common = a.join(b, how="inner", lsuffix="_A", rsuffix="_B")
    if common.empty: return None
    common["Spread"] = common["Price_A"] - common["Price_B"]

    # Weekly X-axis labels
    dates_noyear = [d.strftime("%b %d") if i%5==0 else "" for i,d in enumerate(common.index)]

    plt.figure(figsize=(12,6))
    plt.plot(dates_noyear, common["Spread"], color="blue")
    plt.title(f"2-Month Coffee Spread: {a_path.stem}-{b_path.stem}")
    plt.xlabel("Date (weekly)")
    plt.ylabel("Spread")
    plt.xticks(rotation=45)
    plt.tight_layout()

    chart_file = output_dir / f"{a_path.stem}_{b_path.stem}_spread.png"
    plt.savefig(chart_file, dpi=150)
    plt.close()
    return chart_file.name

def generate_html(results, out_html: Path, charts_dir: Path):
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>"]
    parts.append("<title>2-Month Coffee Spread Charts</title>")
    parts.append("<style>"
                 "body{font-family:Arial;margin:0;padding:0;}"
                 ".chart{text-align:center;margin-bottom:30px;}"
                 "img{max-width:100%;height:auto;}"
                 "</style></head><body>")
    parts.append(f"<h1 style='text-align:center;'>2-Month Coffee Spread Charts</h1>")
    parts.append(f"<p style='text-align:center;font-size:12px;'>Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>")

    for r in results:
        parts.append("<div class='chart'>")
        parts.append(f"<h2>{r['title']}</h2>")
        parts.append(f"<img src='{charts_dir.name}/{r['chart_file']}' alt='{r['title']}'>")
        parts.append("</div>")

    parts.append("</body></html>")
    out_html.write_text("\n".join(parts), encoding="utf-8")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir","-d", default="coffee_data", help="Directory with headerless CSVs")
    parser.add_argument("--out","-o", default="index.html", help="Output HTML file in main dir")
    args = parser.parse_args()

    basedir = Path(args.dir)
    charts_dir = basedir / "charts"
    charts_dir.mkdir(exist_ok=True)

    parsed = scan_csvs(basedir)
    results = []

    for root, entries in parsed.items():
        # Only coffee contracts
        if not root.upper().startswith("KC"):
            continue
        # Filter only coffee month codes H,K,N,U,Z
        entries = [e for e in entries if e["month"] in COFFEE_MONTH_CODES]
        if len(entries)<2:
            continue
        entries = sort_entries(entries)
        # 2-month spreads: skip 1-month
        for i in range(len(entries)-2):
            a = entries[i]["path"]
            b = entries[i+2]["path"]  # skip one month
            try:
                chart_name = make_chart(a, b, charts_dir)
                if chart_name:
                    results.append({"title": f"{a.stem}-{b.stem}", "chart_file": chart_name})
            except Exception as e:
                print(f"Error processing {a} / {b}: {e}")

    out_html = Path(args.out)
    generate_html(results, out_html, charts_dir)
    print(f"Done. HTML written to {out_html}")

if __name__=="__main__":
    main()
