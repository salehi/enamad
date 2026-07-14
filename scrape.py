#!/usr/bin/env python3
"""Threaded scrape of the full enamad DomainListForMIMT table to CSV.

Pure Python (curl_cffi), captcha auto-solved locally. Each worker thread keeps
its own curl_cffi session (thread-local) and they share one read-only Solver, so
pages are fetched in parallel — fast enough to finish inside a GitHub Actions
job. Usage:

    python scrape.py run --threads 12 --out public/enamad_domainlist.csv
    python scrape.py run --end 20 --threads 8      # quick validation
"""
import os, csv, json, time, random, argparse, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from enamad import EnamadHTTP
from solver import Solver

COLUMNS = ["row", "domain", "business_name", "province", "city", "rating",
           "approve_date", "expire_date", "enamad_id", "code", "trustseal_url"]

_tls = threading.local()
_solver = None
_jitter = 0.0


def _client():
    c = getattr(_tls, "client", None)
    if c is None:
        c = EnamadHTTP(solver=_solver)
        _tls.client = c
    return c


def _fetch(page):
    if _jitter:
        time.sleep(random.uniform(0, _jitter))
    res = _client().fetch_page(page)
    return page, res.get("applicantDomainsList", [])


def run(threads, end, out, jitter):
    global _solver, _jitter
    _solver = Solver()
    _jitter = jitter

    boot = EnamadHTTP(solver=_solver)
    r1 = boot.fetch_page(1)
    total = end or int(r1.get("page") or 1)
    _tls.client = boot                      # reuse boot session on this thread
    results = {1: r1.get("applicantDomainsList", [])}
    print(f"total pages: {total}; scraping with {threads} threads", flush=True)

    pages = list(range(2, total + 1))
    failures, done = [], [1]
    lock = threading.Lock()
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(_fetch, p): p for p in pages}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                pg, recs = fut.result()
                with lock:
                    results[pg] = recs
                    done[0] += 1
                    if done[0] % 100 == 0 or done[0] == total:
                        rate = done[0] / (time.time() - t0)
                        print(f"  {done[0]}/{total} pages ({rate:.1f}/s)", flush=True)
            except Exception:
                failures.append(p)

    for p in list(failures):                # one sequential retry sweep
        try:
            _, recs = _fetch(p)
            results[p] = recs
            failures.remove(p)
        except Exception:
            pass

    n = write_csv(results, out)
    took = time.time() - t0
    print(f"DONE: {len(results)}/{total} pages, {n} rows in {took:.0f}s", flush=True)
    if failures:
        print(f"WARNING: {len(failures)} pages failed: {sorted(failures)[:20]}", flush=True)


def write_csv(results, out):
    """Dedupe by enamad id, order by page/row, write UTF-8-BOM CSV."""
    by_id = {}
    for p in sorted(results):
        base = (p - 1) * 30
        for i, r in enumerate(results[p]):
            r["_row"] = base + i + 1
            by_id[r["id"]] = r
    records = sorted(by_id.values(), key=lambda r: r["_row"])

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for n, r in enumerate(records, 1):
            w.writerow([
                n, r.get("domain_address", ""), r.get("persian_name") or "",
                r.get("province") or "", r.get("city") or "", r.get("rating", 0),
                r.get("approve_date") or "", r.get("expire_date") or "",
                r.get("id", ""), r.get("code", ""),
                f"https://Trustseal.enamad.ir/?id={r.get('id')}&code={r.get('code')}",
            ])
    return len(records)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--threads", type=int, default=12)
    r.add_argument("--end", type=int, default=0, help="last page (0 = all)")
    r.add_argument("--out", default="public/enamad_domainlist.csv")
    r.add_argument("--jitter", type=float, default=0.05,
                   help="max random pre-request delay per fetch (politeness)")
    args = ap.parse_args()
    run(args.threads, args.end, args.out, args.jitter)
