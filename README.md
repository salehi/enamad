# enamad

Scrapes the full [enamad.ir DomainListForMIMT](https://www.enamad.ir/DomainListForMIMT)
table (Iran's e-commerce trust-seal registry, ~4700 pages × 30 rows) to a CSV and
publishes it to GitHub Pages as a searchable table.

**Live site:** https://salehi.github.io/enamad/ · **Data:** [`enamad_domainlist.csv`](https://salehi.github.io/enamad/enamad_domainlist.csv)

## How it works

Pure Python, no browser:

- **`enamad.py`** — talks to enamad directly with [`curl_cffi`](https://github.com/lexiforest/curl_cffi)
  impersonating Chrome (matches a real browser's TLS/JA3 fingerprint, so the
  WAF accepts it). Endpoints: `POST /refreshCapt` (captcha + token) and
  `POST /getDomainList` (a results page).
- **`solver.py` + `templates.npz`** — each `getDomainList` needs a captcha. The
  captcha is a fixed 5-char bitmap font; the solver segments it into 5 glyphs and
  classifies each by nearest-neighbour to labelled exemplars
  (**~97% per-captcha** accuracy). Failed solves just retry with a fresh captcha.
- **`scrape.py`** — fetches every page in parallel (thread-local sessions,
  shared read-only solver), dedupes by enamad id, writes a UTF-8 CSV.
- **`make_site.py`** — builds the self-contained `public/index.html` viewer.

## Run locally

```bash
pip install -r requirements.txt
python scrape.py run --threads 12 --out public/enamad_domainlist.csv
python make_site.py
# open public/index.html
```

`python scrape.py run --end 20` scrapes just the first 20 pages (quick test).

## CI

`.github/workflows/scrape.yml` runs the scrape on a **weekly** schedule and
on-demand (**Run workflow**), then deploys the CSV + viewer to GitHub Pages.

> Note: enamad.ir may be geo/sanction-blocked from GitHub-hosted runners. If a CI
> run can't reach it, use a **self-hosted runner** (add `runs-on: self-hosted`).

## CSV columns

`row, domain, business_name, province, city, rating, approve_date, expire_date,
enamad_id, code, trustseal_url`
