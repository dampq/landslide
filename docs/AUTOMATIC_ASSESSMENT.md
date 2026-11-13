# Automatic location-based assessment

The application now has an inspect-then-score coordinate workflow. It reads backend-local rasters using the supplied training definitions and unchanged V1/V2 fitted pipelines. Availability depends on preparing the actual data **on the machine running the API**. The large raster ZIP currently resides in the user's Codespace, not the assistant's workspace. Its file listing was inspected; real-data acceptance here is not claimed.

## Codespace setup

Stop the running development server with Ctrl+C. On the existing integration branch, run:

```bash
git pull --ff-only &&
bash scripts/setup.sh &&
npm run prepare:rasters
```

Do not add `--demo`. The archive must remain at `model-handoff/frnd_raster_data.zip`. The preparation command:

1. Validates archive paths, duplicate entries, allowed dataset directories and disk space. It reads members fully with ZIP CRC checks, writes files atomically, computes SHA-256 checksums, and preserves existing differing files instead of overwriting them.
2. Stores data in ignored `.cache/environmental-data/`, with an inventory covering the source archive and each extracted file. Both that directory and the large raster archive are excluded from Git. Allow roughly 2 GB for the archive plus extracted data, in addition to dependencies; the script checks required free space.
3. Checks required grid metadata against the handoff: EPSG:4326, one band, documented resolution and NoData conventions, and SoilGrids dimensions. A missing local file is an error, not an imputed pixel.
4. Samples event 467 at 26.19 N, 91.71 E, and compares both raw feature sets, transformed vectors and outputs with the supplied reference JSONs. Expected V1 score: **0.7506392613449581**; V2: **0.9369784686315531**. No model is trained or refitted.
5. Writes `ready.json` only after all checks pass. Repeating preparation verifies/reuses identical files. If any check fails, retain the output for diagnosis; don't force different values/checksums or overwrite user data.

A successful result prints `status: verified` with both reference checks matched. Then start:

```bash
npm run dev:clean
```

The clean application database and its accounts/records are retained. Raster preparation does not seed application records. `RASTER_DATA_ROOT` can explicitly select another private local data directory, but it must be supplied consistently to preparation and API startup; there is no automatic `.env` loading.

## Use in the website

As an official/administrator:

- Open **Model integration**, select V1 (default) or V2, and use **Location-based assessment**. Enter coordinates or choose a point in its map. Alternatively, click the main GIS map and follow **Inspect environmental inputs here**.
- Select **Extract environmental inputs**. No model runs at this step. Inspect the values, units, source status, version/date, resolution/CRS, attribution, raw values/scales and source checksums.
- Select **Run inspected assessment** only after inspection. The backend uses the stored extraction, checks its owner, age (one hour), current source inventory and used-file checksums, then calls the matching original model pipeline. A client cannot replace inspected values in the run request. Repeated run requests return the existing result rather than duplicating history.
- Review the relative score and imputed fields. Results retain their coordinates, source provenance, extraction timestamp, inventory/source archive fingerprints, model version and artifact checksums in prediction history. The supplied-example panel remains separate and never substitutes values when local data are missing.

The API routes are `POST /api/assessment/features` with `{lat, lng, modelVersion}` and `POST /api/assessment/run` with `{extractionId}`. Both require official/admin authentication; raw raster files and absolute server paths are not exposed. Source previews are private server records. Model scoring does not publish warnings or dispatch teams.

## Exact sampling and missing-data rules

The uploaded extraction handoff is preserved as `model-handoff/Feature_Extraction_Handoff.zip` with a SHA-256 pin. Original scripts inside it are provenance references and are never executed for training. Its reconstructed sampler was reviewed against the originals. This implementation uses containing-pixel Rasterio sampling, source-grid CRS and half-open pixel bounds; no interpolation or fabricated feature extraction occurs.

- WorldCover uses the first covering supplied tile. Only categories represented by the model are scoreable. Missing land cover prevents both models from scoring.
- Soil clay/sand source values are divided by 1000, pH by 10, SOC is passed unchanged. The original V1 pH sentinel invalidates the entire soil vector for encoded pH <=0 or >140. Importantly, the original script invalidates **both** clay and sand if either exceeds 1000; the reconstructed handoff adapter handles them separately. This integration follows the original training code.
- V2 reads the supplied BIO, elevation, slope and aspect-component rasters directly. It does not recalculate terrain using a different algorithm or substitute live rainfall. Aspect degrees are an intermediate, not a model input.
- Source NoData/out-of-grid values remain null with diagnostics. V1 blocks scoring with missing required fields. V2 allows null continuous values and uses only the saved imputer; missing files are never interpreted as valid NoData pixels. Invalid/out-of-range feature values block scoring.
- Coordinates outside the supplied eight-state boundary are rejected. Bengaluru coordinates from an incident report, for example, are outside this model's study area even though incident reporting/response itself can store them.

## Provenance and scientific limits

See the supplied source manifest/specifications in the extraction ZIP. WorldCover 2021 and modelled SoilGrids/WorldClim surfaces are not live observations. V2 BIO inputs represent 1970–2000 normals; terrain is about 1 km. Source dates, scales and attribution are preserved. WorldClim use/redistribution restrictions remain applicable; local availability is not permission to publish the underlying rasters.

**SOC caveat:** the supplied handoff calls `soc_0-5cm_Q0.5` a stock in t/ha and the training script passes its raw value unchanged. This code preserves that training convention, rather than inventing a stock/concentration conversion. TIFF unit tags were reported absent; its physical stock/concentration interpretation is not independently established by prediction parity and must be confirmed against authoritative source metadata before scientific interpretation. The UI discloses this caveat.

Matching event 467 is an in-sample reproducibility check, not independent model validation. Source checksums identify the provided files and subsequent changes; without independently supplied provider checksums they do not prove source authenticity. Scores remain experimental presence-background values, not calibrated probabilities, imminent-event forecasts or official warnings. V1 stays default and V2 an experimental comparison.

## Verification evidence

Synthetic GeoTIFF tests check raster mechanics, CRS transformation, pixel edges, masks, sentinel rules, per-version missing-file behaviour, tamper/stale detection, safe repeatable extraction, HTTP permissions and preview-to-score persistence. These tests do not claim to sample the user's real dataset. Real-data verification is performed only by `npm run prepare:rasters` in the Codespace; its output must be checked before claiming that workflow ready there.
