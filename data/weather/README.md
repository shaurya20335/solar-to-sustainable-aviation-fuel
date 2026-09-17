# Arizona weather input

The supplied NSRDB single-axis weather input is versioned as `arizona_nsrdb_2024_site_326317.csv.gz`. It contains the complete **8,784-hour 2024 leap year** for site **326317**, near **33.41° N, 111.94° W** in Arizona.

The model uses metadata `Time Zone=0` (UTC) for timestamps; site local offset `-7` is not the timestamp timezone. All original columns, metadata, precision and row order are preserved exactly. The archive is read directly, without extraction.

| Property | Value |
|---|---|
| Original filename | `2024-326317-one_axis.csv` |
| Uncompressed bytes | `178156331` |
| Compressed bytes | `78209292` |
| Uncompressed SHA-256 | `1e5c3c6149d3665aa57c43c971af6be9319dfae8c74ec0a3654aa11ad485e388` |

The weather file was supplied with the course project. No new weather download or substitution was made during GitHub preparation. Compression uses a fixed gzip timestamp for reproducible packaging. An uncompressed copy may remain locally but is ignored by Git.

Optional extraction: run `gzip -dk data/weather/arizona_nsrdb_2024_site_326317.csv.gz` from the repository root when the CSV does not already exist. The model also accepts a plain CSV via `--solar path/to/weather.csv`.

Upstream data provider: [National Solar Radiation Database](https://nsrdb.nlr.gov/). The [project bibliography](../../docs/references.md) includes the provider-recommended data citation. This dataset retains its original applicable terms and is not relicensed by the project software license.
