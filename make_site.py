#!/usr/bin/env python3
"""Generate public/index.html from the Jinja template site.html.j2 — a
self-contained searchable/paginated viewer for the scraped CSV (loads
enamad_domainlist.csv client-side, renders 50 rows/page).

The template is English chrome only; row data (Persian names, cities, Jalali
dates) is rendered by the browser exactly as scraped.
"""
import os
import argparse
import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = "site.html.j2"


def count_rows(csv_path):
    if not os.path.exists(csv_path):
        return 0
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def render_html(csv_path):
    env = Environment(
        loader=FileSystemLoader(HERE),
        autoescape=select_autoescape(["html", "j2"]),
    )
    rows = count_rows(csv_path)
    updated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = env.get_template(TEMPLATE).render(rows=f"{rows:,}", updated=updated)
    return html, rows


def main(csv_path, out_html):
    html, rows = render_html(csv_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_html)), exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out_html} ({rows} rows)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="public/enamad_domainlist.csv")
    ap.add_argument("--out", default="public/index.html")
    args = ap.parse_args()
    main(args.csv, args.out)
