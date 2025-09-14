import os
import requests
from datetime import datetime

# === CONFIG ===
BASE_URL = (
    "https://webapp-proxy.aws.barchart.com/v1/proxies/timeseries/historical/queryeod.ashx"
    "?symbol={contract}&data=daily&maxrecords=120&volume=total&order=asc"
    "&dividends=false&backadjust=false&daystoexpiration=1&contractroll=expiration"
    "&username=demochartsnew_rt&password=demochartsnew"
)
SYMBOL = "KC"  # Coffee futures root
OUTPUT_DIR = "coffee_data"
INDEX_FILE = "index.html"

# Coffee contract months (ICE: Mar, May, Jul, Sep, Dec)
MONTH_CODES = ["H", "K", "N", "U", "Z"]

# How many years back
YEARS_BACK = 5


def get_contracts(years_back=YEARS_BACK):
    """Generate all KC futures contracts for the last N years."""
    contracts = []
    now = datetime.now()
    current_year = now.year
    start_year = current_year - years_back

    for year in range(start_year, current_year + 1):
        yy = str(year)[-2:]  # 2-digit year
        for code in MONTH_CODES:
            contracts.append(f"{SYMBOL}{code}{yy}")
    return contracts


def download_contract(contract):
    """Download a single contract file from the ashx URL."""
    url = BASE_URL.format(contract=contract)
    filename = os.path.join(OUTPUT_DIR, f"{contract}.csv")

    print(f"Fetching {contract} → {url}")  # log full URL

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        if b"Invalid" in r.content or len(r.content) < 50:
            print(f"No data for {contract}")
            return None
        with open(filename, "wb") as f:
            f.write(r.content)
        print(f"Downloaded {contract}")
        return filename
    except Exception as e:
        print(f"Failed {contract}: {e}")
        return None


def make_index(files):
    """Generate index.html with links to all downloaded files."""
    with open(INDEX_FILE, "w") as f:
        f.write("<html><body>\n<h2>Coffee Futures Data (KC)</h2>\n<ul>\n")
        for file in files:
            if file:
                name = os.path.basename(file)
                f.write(f'<li><a href="{OUTPUT_DIR}/{name}">{name}</a></li>\n')
        f.write("</ul>\n</body></html>\n")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    contracts = get_contracts()
    downloaded_files = [download_contract(c) for c in contracts]
    make_index([f for f in downloaded_files if f])


if __name__ == "__main__":
    main()
