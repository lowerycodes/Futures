#!/usr/bin/env python3
"""
Generate 2-month coffee spreads from headerless CSVs as daily OHLC charts.
- Only KC contracts.
- Only coffee month codes: H, K, N, U, Z
- Skip 1-month spreads (entries[i] + entries[i+2])
- Output PNG charts in coffee_data/charts
- Generate index.html in main directory referencing PNGs
- OHLC candlesticks colored by daily movement with Close line overlay
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import re
import mplfinance as mpf

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
    df = df[["date","open","high","low","close"]].dropna()
    df = df.rename(columns={"date":"Date","open":"Open","high":"High","low":"Low","close":"Close"})
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.sort_values("Date").drop_duplicates("Date")
    df = df.set_index("Date")
    return df

def make_ohlc_chart(a_path, b_path, output_dir: Path):
    a = read_series(a_path)
    b = read_series(b_path)
    
    # Align by date
    df = a.join(b, how="inner", lsuffix="_A", rsuffix="_B")
    if df.empty:
        return None
    
    # Spread OHLC
    ohlc = pd.DataFrame({
        "Open": df["Open_A"] - df["Open_B"],
        "High": df["High_A"] - df["High_B"],
        "Low": df["Low_A"] - df["Low_B"],
        "Close": df["Close_A"] - df["Close_B"]
    }, index=df.index)

    chart_file = output_dir / f"{a_path.stem}_{b_path.stem}_ohlc.png"

    # Plot candlestick OHLC with Close line (use 'linewidths' instead of 'linewidth')
    mpf.plot(
        ohlc,
        type="candle",
        style="charles",
        addplot=mpf.make_addplot(ohlc["Close"], color="blue", linewidths=1.5),
        volume=False,
        tight_layout=True,
        ylabel="Spread",
        datetime_format="%b %d",
        savefig=dict(fname=chart_file, dpi=150)
    )
    return chart_file.name

def generate_html(results, out_html: Path, charts_dir: Path):
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>"]
    parts.append("<title>2-Month Coffee Spread Charts</title>")
    parts.append("<style>"
                 "body{font-family:Arial;margin:0;padding:0;}"
                 ".chart{text-align:center;margin-bottom:30px;}"
                 "img{max-width:100%;height:auto;}"
                 "</style></head><body>")
    parts.append(f"<h1 style='text-align:center;'>2-Month Coffee Spread Charts (OHLC)</h1>")
    parts.append(f"<p style='text-align:center;font-size:12px;'>Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>")

    for r in results:
        parts.append("<div class='chart'>")
        parts.append(f"<h2>{r['title']}</h2>")
        parts.append(f"<img src='coffee_data/charts/{r['chart_file']}' alt='{r['title']}'>")
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
        if not root.upper().startswith("KC"):
            continue
        entries = [e for e in entries if e["month"] in COFFEE_MONTH_CODES]
        if len(entries)<2:
            continue
        entries = sort_entries(entries)
        # 2-month spreads: skip 1-month
        for i in range(len(entries)-2):
            a = entries[i]["path"]
            b = entries[i+2]["path"]
            try:
                chart_name = make_ohlc_chart(a, b, charts_dir)
                if chart_name:
                    results.append({"title": f"{a.stem}-{b.stem}", "chart_file": chart_name})
            except Exception as e:
                print(f"Error processing {a} / {b}: {e}")

    out_html = Path(args.out)
    generate_html(results, out_html, charts_dir)
    print(f"Done. HTML written to {out_html}")

if __name__=="__main__":
    main()
