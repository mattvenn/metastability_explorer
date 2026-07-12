# Flip-flop metastability explorer

[![Made with Claude](https://img.shields.io/badge/Made%20with-Claude-D97757?logo=anthropic&logoColor=white)](https://claude.com/claude-code)

A single, self-contained **`index.html`** for exploring setup/hold violations
and metastability in a real SKY130 D flip-flop, from transistor-level SPICE.
No install, no dependencies, no network calls — just open the file in a browser
(or host it anywhere). Built for the
[Zero to ASIC course](https://ZeroToASICcourse.com).

It's a zero-install web reworking of the original desktop demo,
**[mattvenn/flipflop_demo](https://github.com/mattvenn/flipflop_demo)** — the
SPICE decks and schematic come from there.

`index.html` already has all the simulation data embedded (compressed), so you
only need the steps below if you want to **regenerate** it from new SPICE runs.

## What's in here

| Path | What it is |
|------|------------|
| `index.html` | The finished, self-contained page — this is what you host |
| `index_before.html` | Baseline-only snapshot (no ultra-fine data), for before/after comparison |
| `build/` | The generator: `gendata.py`, `template.html`, `build/README.md` |
| `zerotoasic/` | z2a branding assets (logos etc.) |
| `flipflop_demo/` | SPICE decks + schematic — **git-ignored** here; local reference only, independently versioned at <https://github.com/mattvenn/flipflop_demo> |

## Regenerating the data

The page is built in three steps: two SPICE simulations produce CSVs, then a
Python script merges and embeds them into `index.html`.

### Prerequisites
- **ngspice 44+**
- **sky130 PDK** — e.g. the OSIC / foss Docker image. The decks reference
  `/foss/pdks/sky130A/...`; edit the `.lib` / `.include` lines at the top of each
  deck for your PDK path.
- **Python 3** with **numpy**

### 1. Coarse baseline sweep
Sweeps a 300 ps data pulse past the clock edge in 0.5 ps steps — 1801 runs,
~8 min. From `flipflop_demo/spice/`:
```
mkdir -p csv
ngspice simulation.spice          # -> csv/0 .. csv/1800
```
(Shortcut: the repo ships `csv.tar.bz2`; `tar xf csv.tar.bz2` gives a ready-made
`csv/`, though re-running the deck is the canonical source.)

### 2. Ultra-fine edge zoom
Bisects each setup/hold edge to its metastable balance point, then fans runs
from 2 ps down to ~2 fs around it — ~30 runs, ~1 min. From `flipflop_demo/spice/`:
```
mkdir -p csv_fine
ngspice simulation_fine.spice     # -> csv_fine/0 .. (each carries its exact delay)
```

### 3. Build the page
Merges baseline + fine runs, sorts by data-pulse delay, quantizes, delta-encodes,
gzips + base64-embeds, and assembles the page. From `build/`:
```
python3 gendata.py                              # -> ../index.html
python3 gendata.py --no-fine index_before.html  # baseline-only snapshot (optional)
```
See `build/README.md` for the encoding details.

## How 197 MB becomes ~220 KB

Every run is kept — nothing is downsampled away. Each is resampled onto a common
800-point / 0–4 ns grid, quantized to 1 byte, and delta-encoded across **both**
run and time (adjacent runs and adjacent samples are nearly identical, so ~99% of
the bytes become zeros), then gzipped and base64-embedded. The browser inflates
the blob natively via `DecompressionStream('gzip')` and undoes the deltas in a
few lines of JavaScript.
