#!/usr/bin/env python3
"""Stream Land Registry Price Paid yearly files and keep only Greater London rows.

PPD columns (no header):
0 tx_id, 1 price, 2 date, 3 postcode, 4 prop_type, 5 old_new, 6 duration,
7 PAON, 8 SAON, 9 street, 10 locality, 11 town, 12 district, 13 county,
14 ppd_category, 15 record_status
"""
import csv
import io
import subprocess
import sys

BASE = "http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-{year}.csv"
OUT = "data/london_ppd.csv"
YEARS = range(2006, 2027)

def main():
    with open(OUT, "w", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(["price", "date", "prop_type", "old_new", "duration", "district", "ppd_category"])
        for year in YEARS:
            url = BASE.format(year=year)
            kept = total = 0
            proc = subprocess.Popen(
                ["curl", "-sfL", "--retry", "3", url],
                stdout=subprocess.PIPE,
            )
            reader = csv.reader(io.TextIOWrapper(proc.stdout, encoding="utf-8", errors="replace"))
            for row in reader:
                if len(row) < 16:
                    continue
                total += 1
                if row[13].strip().upper() == "GREATER LONDON":
                    kept += 1
                    w.writerow([row[1], row[2][:10], row[4], row[5], row[6], row[12].strip().title(), row[14]])
            rc = proc.wait()
            print(f"{year}: total={total} london={kept} curl_rc={rc}", flush=True)
            if rc != 0 and year < 2026:
                print(f"WARNING: download failed for {year}", flush=True)

if __name__ == "__main__":
    main()
