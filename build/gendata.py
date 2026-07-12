#!/usr/bin/env python3
"""Merge coarse baseline (csv/) + ultra-fine edge fan (csv_fine/) into one
delay-sorted dataset, encode compactly, and write payload.json for index.html."""
import os, gzip, base64, json, sys
import numpy as np

# Optional: `--no-fine` skips the ultra-fine fan (baseline-only, i.e. "before").
# Optional: a trailing non-flag arg sets the output filename (default index.html).
NOFINE = "--no-fine" in sys.argv
OUTNAME = next((a for a in sys.argv[1:] if not a.startswith("-")), "index.html")

ROOT = "/Users/mattvenn/asic/metastability_webpage"
BASE = os.path.join(ROOT, "flipflop_demo/spice/csv")
FINE = os.path.join(ROOT, "flipflop_demo/spice/csv_fine")
SCHEM = os.path.join(ROOT, "flipflop_demo/schematic/tgff_with_clock.png")
LOGO_BLACK = os.path.join(ROOT, "zerotoasic/z2a-logo-black-transp.png")
LOGO_WHITE = os.path.join(ROOT, "zerotoasic/z2a-logo-white-transp.png")
OUT = os.path.dirname(os.path.abspath(__file__))

GRID = 800
TSTOP = 4e-9                      # common window (everything resolves within 4ns)
DELAY0_PS = 800.0
DSTEP_PS = 0.5

SIGNALS = [   # colours match the schematic node dots exactly
    ("Q",           "#FF8C00"),
    ("D",           "#E81123"),
    ("CLK",         "#EC008C"),
    ("CLK_INV",     "#68217A"),
    ("CLK_INV_INV", "#00188F"),
    ("D_INV",       "#00BCF2"),
    ("X2_IN",       "#00B294"),
    ("X2_OUT",      "#009E49"),
]
NSIG = len(SIGNALS)
time = np.linspace(0.0, TSTOP, GRID)

def resample(d):
    """d: raw ngspice table. Return (NSIG, GRID) resampled onto common grid."""
    t = d[:, 0]
    out = np.empty((NSIG, GRID))
    for c in range(NSIG):
        out[c] = np.interp(time, t, d[:, 1 + c])
    return out

runs = []  # (delay_ps, sig[NSIG,GRID], source)

# ---- coarse baseline: uniform delay = 800 + 0.5*index ----
bfiles = sorted([f for f in os.listdir(BASE) if f.isdigit()], key=int)
for i, fn in enumerate(bfiles):
    d = np.loadtxt(os.path.join(BASE, fn), skiprows=1)
    runs.append((DELAY0_PS + i * DSTEP_PS, resample(d), "base"))
print("baseline runs:", len(bfiles))

# ---- ultra-fine fan: delay carried in the last column ----
if NOFINE:
    print("fine runs: skipped (--no-fine)")
else:
    ffiles = sorted([f for f in os.listdir(FINE) if f.isdigit()], key=int)
    for fn in ffiles:
        d = np.loadtxt(os.path.join(FINE, fn), skiprows=1)
        dly = float(d[0, -1] * 1e12)      # last column is the constant delay (s -> ps)
        runs.append((dly, resample(d[:, :NSIG + 1]), "fine"))
    print("fine runs:", len(ffiles))

# ---- sort by delay, drop exact duplicates ----
runs.sort(key=lambda r: r[0])
merged = []
for r in runs:
    if merged and abs(r[0] - merged[-1][0]) < 1e-7:   # <1e-7 ps = truly identical
        continue
    merged.append(r)
nruns = len(merged)
delays = np.array([r[0] for r in merged])
arr = np.stack([r[1] for r in merged], axis=0)        # (nruns, NSIG, GRID)
nfine = sum(1 for r in merged if r[2] == "fine")
print("merged runs: %d (%d fine kept)  delay span %.1f..%.1f ps"
      % (nruns, nfine, delays.min(), delays.max()))

lo = float(arr.min()); hi = float(arr.max())
print("V range [%.3f, %.3f]" % (lo, hi))

# ---- danger bands: runs whose Q resolves slower than the ~baseline settle ----
Q = arr[:, 0, :]; qf = Q[:, -1]
settle = np.zeros(nruns)
for i in range(nruns):
    dev = np.abs(Q[i] - qf[i]) > 0.09
    idx = np.where(dev)[0]
    settle[i] = time[idx[-1]] if len(idx) else 0.0
baseline = float(np.median(settle))
elevated = settle > baseline + 0.028e-9
bands = []
i = 0
while i < nruns:
    if elevated[i]:
        j = i
        while j < nruns and elevated[j]:
            j += 1
        if j - i >= 2:
            bands.append([max(0, i - 6), min(nruns - 1, j - 1 + 6)])
        i = j
    else:
        i += 1
print("bands (run idx):", bands, "delays:",
      [[round(delays[b[0]], 3), round(delays[b[1]], 3)] for b in bands])

# focus = the exact flip run indices (where Q outcome changes) - the knife edges
low = qf < 0.9
flips = [int(x) for x in np.where(np.diff(low.astype(int)) != 0)[0]]
if len(flips) < 2:
    flips = [(b[0] + b[1]) // 2 for b in bands]
print("focus (flip run idx):", flips, "delays:", [round(delays[f], 4) for f in flips])

# ---- quantize + double delta + gzip ----
q = np.round((arr - lo) / (hi - lo) * 255.0).astype(np.uint8)
q = q.transpose(0, 1, 2)                               # (run, sig, time) already
R = q.copy(); R[1:] = (q[1:].astype(np.int16) - q[:-1].astype(np.int16)).astype(np.uint8)
T = R.copy(); T[:, :, 1:] = (R[:, :, 1:].astype(np.int16) - R[:, :, :-1].astype(np.int16)).astype(np.uint8)
raw = T.tobytes(order="C")
blob = gzip.compress(raw, 9)
b64 = base64.b64encode(blob).decode()
print("payload gzip=%.1fKB base64=%.1fKB" % (len(blob) / 1e3, len(b64) / 1e3))

# round-trip check
dec = np.frombuffer(gzip.decompress(blob), dtype=np.uint8).astype(np.uint16).reshape(nruns, NSIG, GRID).copy()
dec = np.cumsum(dec, axis=2).astype(np.uint16) & 0xFF
dec = np.cumsum(dec, axis=0).astype(np.uint16) & 0xFF
print("round-trip max err:", int(np.abs(dec.astype(np.int16) - q.astype(np.int16)).max()))

def b64file(p):
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()

payload = {
    "nruns": nruns, "grid": GRID, "nsig": NSIG,
    "lo": lo, "hi": hi, "tstop": TSTOP,
    "delays": [round(x, 6) for x in delays.tolist()],
    "nfine": nfine,
    "signals": [{"name": n, "color": c} for (n, c) in SIGNALS],
    "bands": bands,
    "focus": flips,
    "data_b64": b64,
    "schematic_b64": b64file(SCHEM),
    "logo_black_b64": b64file(LOGO_BLACK),
    "logo_white_b64": b64file(LOGO_WHITE),
}
with open(os.path.join(OUT, "payload.json"), "w") as f:
    json.dump(payload, f)
print("wrote payload.json (%.1f KB)" % (os.path.getsize(os.path.join(OUT, "payload.json")) / 1e3))

# ---- assemble the self-contained index.html ----
tpl = open(os.path.join(OUT, "template.html")).read()
assert "/*__PAYLOAD__*/" in tpl, "template.html missing /*__PAYLOAD__*/ token"
dst = os.path.join(ROOT, OUTNAME)
with open(dst, "w") as f:
    f.write(tpl.replace("/*__PAYLOAD__*/", json.dumps(payload)))
print("wrote %s (%.1f KB)" % (dst, os.path.getsize(dst) / 1e3))
