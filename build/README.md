# Build: metastability explorer webpage

Generates the self-contained `../index.html` from the SPICE simulation output.

## Inputs
- `../flipflop_demo/spice/csv/`      — coarse baseline sweep (`simulation.spice`), 1801 runs, 0.5 ps steps
- `../flipflop_demo/spice/csv_fine/` — ultra-fine edge fan (`simulation_fine.spice`), ~30 runs, down to ~10 fs
- `../flipflop_demo/schematic/tgff_with_clock.png`, `../zerotoasic/z2a-logo-*.png`
- `template.html`                    — the page shell, with a `/*__PAYLOAD__*/` token

## Run
```
python3 gendata.py
```
This:
1. resamples every run onto a common 800-pt / 0–4 ns grid,
2. merges baseline + fine runs, sorts by data-pulse delay, drops duplicates,
3. quantizes to 1 byte, delta-encodes across run+time, gzips, base64s (~220 KB),
4. finds the two metastable danger bands and flip ("focus") points,
5. writes `payload.json` and assembles `../index.html`.

The browser inflates the blob natively via `DecompressionStream('gzip')` and undoes the
deltas in JS — no runtime dependencies, no network calls (except the YouTube embed).

## Regenerating the SPICE data
See `../flipflop_demo/spice/`: `simulation.spice` (coarse) then `simulation_fine.spice`
(fine, into `csv_fine/`). Both need the sky130 PDK path set at the top. ngspice 44+.
