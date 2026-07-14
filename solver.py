#!/usr/bin/env python3
"""Captcha solver for enamad DomainList captchas (template / 1-NN).

The captcha is a fixed 90x40 bitmap font: 5 chars (A-Z0-9) drawn as segmented
bars in a fixed top band (rows ~10-27), with two smaller watermarks safely
below it. Because the font and character positions are fixed, we:

  1. crop the main-text band and binarise (glyph ink -> white),
  2. slice it into 5 evenly-spaced character cells,
  3. crop+resize each cell to a canonical bitmap,
  4. classify each glyph by nearest-neighbour to labelled exemplars.

Exemplars were learned from a 1000-image server-verified dataset (~97% captcha
accuracy on held-out data) and are bundled in templates.npz.
"""
import os
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "templates.npz")

# main-text band and canonical glyph size (must match how templates were built)
Y0, Y1 = 10, 27
XMAX = 62            # ignore the watermark region to the right when finding x-extent
CH, CW = 22, 16      # canonical glyph height / width


def _load_gray(png_bytes):
    return cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)


def _binarize_band(gray):
    band = gray[Y0:Y1, :]
    _, bw = cv2.threshold(band, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if (bw == 255).sum() > (bw == 0).sum():   # ink is the minority -> white
        bw = 255 - bw
    return bw


def _crop_resize(cell):
    ys, xs = np.where(cell > 0)
    if len(xs) == 0:
        return np.zeros((CH, CW), np.float32)
    crop = cell[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    r = cv2.resize(crop, (CW, CH), interpolation=cv2.INTER_AREA)
    return (r > 127).astype(np.float32)


def segment(png_bytes):
    """Return 5 canonical glyph arrays (CH x CW float 0/1), or None on failure."""
    gray = _load_gray(png_bytes)
    if gray is None or gray.shape[0] < Y1:
        return None
    bw = _binarize_band(gray)
    colink = (bw[:, :XMAX] > 0).sum(axis=0)
    xs = np.where(colink > 0)[0]
    if len(xs) < 5:
        return None
    x0, x1 = int(xs[0]), int(xs[-1]) + 1
    W = x1 - x0
    return [_crop_resize(bw[:, x0 + round(i * W / 5):x0 + round((i + 1) * W / 5)])
            for i in range(5)]


class Solver:
    """1-NN template matcher. Thread-safe (numpy reads only)."""

    def __init__(self, templates_path=TEMPLATES):
        d = np.load(templates_path, allow_pickle=True)
        self.X = d["X"].astype(np.float32)    # (n_glyphs, CH*CW) exemplars
        self.y = d["y"]                       # (n_glyphs,) char labels

    def classify_glyph(self, glyph):
        v = glyph.reshape(-1)
        return str(self.y[int(np.argmin(((self.X - v) ** 2).sum(axis=1)))])

    def solve(self, png_bytes):
        glyphs = segment(png_bytes)
        if glyphs is None:
            return ""
        return "".join(self.classify_glyph(g) for g in glyphs)


_default = None


def solve(png_bytes):
    global _default
    if _default is None:
        _default = Solver()
    return _default.solve(png_bytes)
