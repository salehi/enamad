#!/usr/bin/env python3
"""Pure-Python enamad client — no browser.

Talks to enamad.ir directly with curl_cffi, impersonating Chrome at the TLS/HTTP
layer so the fingerprint matches a real browser (gets past WAF/JA3 checks that
plain requests trips). Captchas are solved locally with the bundled template
solver.

    from enamad import EnamadHTTP
    e = EnamadHTTP()
    res = e.fetch_page(1)      # captcha auto-solved
"""
import time
import base64

from curl_cffi import requests

from solver import Solver

BASE = "https://www.enamad.ir"
PAGE_URL = BASE + "/DomainListForMIMT"

# form fields exactly as the site's own getDomainList call sends them
_EMPTY_FILTERS = {
    "s#ms-domain-address": "", "s#ms-persian-name": "",
    "s#ms-product-service-id-enc": "", "s#mi-rating": "",
    "s#ms-province-id-enc": "", "s#ms-city-id-enc": "",
    "Csearch": "",
}


class EnamadHTTP:
    def __init__(self, solver=None, impersonate="chrome", timeout=30):
        self.timeout = timeout
        self.impersonate = impersonate
        self.solver = solver or Solver()
        self.session = requests.Session(impersonate=impersonate)
        self._bootstrap()

    def _bootstrap(self):
        """GET the page once so the session picks up any cookies the endpoints
        expect (mirrors a browser's first load)."""
        r = self.session.get(PAGE_URL, timeout=self.timeout)
        r.raise_for_status()

    def _ajax_headers(self):
        return {"X-Requested-With": "XMLHttpRequest",
                "Referer": PAGE_URL, "Origin": BASE}

    def refresh_captcha(self):
        """Return (cptToken, png_bytes) for a fresh captcha."""
        r = self.session.post(
            BASE + "/refreshCapt",
            headers={**self._ajax_headers(),
                     "Content-Type": "application/json; charset=UTF-8"},
            data="{}", timeout=self.timeout)
        r.raise_for_status()
        d = r.json()
        return d["cptToken"], base64.b64decode(d["captha"])

    def get_domain_list(self, page, capt, token):
        """POST getDomainList; return parsed JSON (result==1 on success)."""
        data = dict(_EMPTY_FILTERS)
        data.update({"Capt": capt, "page": str(page),
                     "token": token, "cptToken": token, "checkcapga": "1"})
        r = self.session.post(
            BASE + "/getDomainList",
            headers={**self._ajax_headers(),
                     "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            data=data, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def fetch_page(self, page, max_attempts=8):
        """Fetch one results page, auto-solving the captcha; retry with a fresh
        captcha until the server accepts. Rebuilds the session on errors.
        Returns the parsed getDomainList JSON. Raises after max_attempts."""
        for attempt in range(1, max_attempts + 1):
            try:
                tok, png = self.refresh_captcha()
                guess = self.solver.solve(png)
                if guess:
                    res = self.get_domain_list(page, guess, tok)
                    if res.get("result") == 1:
                        return res
            except Exception:
                time.sleep(min(1.0 * attempt, 6))
                try:
                    self.session = requests.Session(impersonate=self.impersonate)
                    self._bootstrap()
                except Exception:
                    pass
                continue
            time.sleep(0.1)
        raise RuntimeError(f"failed to solve captcha for page {page} "
                           f"after {max_attempts} attempts")


if __name__ == "__main__":
    e = EnamadHTTP()
    res = e.fetch_page(1)
    lst = res.get("applicantDomainsList", [])
    print(f"page1: {len(lst)} rows, totalPages={res.get('page')}, "
          f"first={lst[0]['domain_address'] if lst else None}")
