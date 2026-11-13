# Location-based inference: feature-to-source contract

**Current update:** the extraction handoff and matching raster file listing have now been supplied. The initial feasibility assessment below is preserved as history. The implemented local extraction workflow, resolved training definitions, SOC interpretation caveat and real-data acceptance gate are documented in [AUTOMATIC_ASSESSMENT.md](AUTOMATIC_ASSESSMENT.md). Real-raster verification must run in the Codespace hosting the datasets.

Prepared 13 November 2026 **before implementing extraction**. Authoritative inputs are the supplied feature lists, metadata, helpers and fitted pipelines in `model-handoff/Ashtaraksha_Teammate_Handoff.zip`. V1 remains default; V2 is experimental. Training, replacement and changes to either estimator/pipeline belong to the model team and are outside this website task.

## Evidence and access status

The archive was accessed locally and its version files are fingerprinted in `model-handoff/manifest.json`. It contains no training CSVs, source rasters, sampling code or terrain derivation code. Existing real inference accepts manually supplied features; automatic coordinate-to-feature extraction is **not implemented or validated**.

HEAD requests on 13 November 2026 to the following destinations all failed with proxy CONNECT 403. No provider documentation or raster was retrieved. See `evidence/source-access.json`. Product descriptions and terms below come from the supplied metadata/reports; they are not newly verified provider claims.

- ESA WorldCover: https://esa-worldcover.org/en/data-access
- SoilGrids: https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs.html
- WorldClim documentation: https://www.worldclim.org/data/worldclim21.html
- Exact BIO archive identified by teammate: https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_2.5m_bio.zip
- Exact elevation archive identified by teammate, **identified only, not probed**: https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_30s_elev.zip

The first four hosts are proposed in the environment draft, preserving existing weather/map rules. This does not apply access or confirm availability. Provider download/CDN hosts will need identification and fresh checks after documentation becomes accessible.

## Feature table

All rows cover North East India in principle through their parent products; actual pilot tile coverage, CRS, affine transforms, masks, geolocation alignment and acquisition metadata remain unverified until files are obtained. Nominal WorldCover/SoilGrids resolutions below are product expectations to verify from file headers, not measurements of downloaded files. Soil products are modelled estimates, WorldCover is a classified surface, WorldClim is modelled long-term climate/elevation context, and terrain derivatives are derived values. None are live observations or soil-moisture measurements.

| Model | Required field | Definition / model-ready encoding | Candidate permitted source and licence reported in handoff | Resolution and date | Proposed location extraction / unresolved compatibility detail | Missing policy |
|---|---|---|---|---|---|---|
| Both | `worldcover_class` | Integer categorical code; only 10,30,40,50,60,70,80,90,100 represented in training; pipeline one-hot encodes into nine categories | ESA WorldCover 2021 v200; CC BY 4.0 | Nominal 10 m; 2021 | Transform WGS84 point to source CRS, select containing pixel, nearest/categorical sampling only. Exact pilot tile/release URL and training sampling convention still needed. Code 20 remains unsupported even if valid in the source product. | Block both versions when missing or unsupported; never choose another class |
| Both | `clay_fraction` | SoilGrids 0–5 cm clay, source per-mille divided by 1000; 0–1 | ISRIC SoilGrids 2.0; CC BY 4.0 | Nominal 250 m; static modelled soil product, exact release/statistic unconfirmed | Sample matching clay layer/depth/statistic and apply scale once; confirm training used mean versus another statistic and source resampling | V1 block; V2 explicit null, fitted median imputation and disclosure |
| Both | `sand_fraction` | SoilGrids 0–5 cm sand, per-mille /1000; 0–1 | ISRIC SoilGrids 2.0; CC BY 4.0 | Nominal 250 m; exact release/statistic unconfirmed | Same controls as clay; not percent /100 and not moisture | V1 block; V2 null + disclose |
| Both | `soil_ph` | SoilGrids pH in water; source pH×10 divided by 10. V1 >0–14; V2 0–14 | ISRIC SoilGrids 2.0; CC BY 4.0 | Nominal 250 m; 0–5 cm, exact release/statistic unconfirmed | Training metadata says encoded pH zero indicated missing entire soil vector because WCS TIFF lacked nodata. Confirm and reproduce this rule for extraction; do not treat zero source pH as a real measurement | V1 block missing soil vector; V2 null + disclose |
| Both | `soc_stock_t_ha` | Nonnegative soil organic-carbon **stock**, tonnes/hectare; not SOC concentration | ISRIC SoilGrids 2.0; CC BY 4.0 | Nominal 250 m; **exact stock product/depth/statistic is not specified sufficiently** | Obtain original product URL/manifest and conversion. Do not assume SOC g/kg equals stock or invent bulk-density/depth conversion; confirm whether this is a separate stock product rather than a 0–5 cm layer | V1 block; V2 null + disclose |
| V2 | `bio12_annual_precipitation_mm` | Annual precipitation normal, mm/year; nonnegative | WorldClim 2.1 BIO12, exact BIO archive above; academic/non-commercial, redistribution/commercial use requires permission | 2.5 arc-minute (~4.6 km); 1970–2000 normal | Sample BIO12 at point using training sampling convention; verify units/scale/mask; never replace with current or annual measured rainfall | Explicit null + fitted median; disclose |
| V2 | `bio13_wettest_month_precip_mm` | Wettest-month precipitation normal, mm/month; nonnegative | Same BIO archive, BIO13; same terms | Same | Sample BIO13, not last month's rain | Null + disclose |
| V2 | `bio15_precipitation_seasonality_pct` | Coefficient of variation, percent; nonnegative | Same BIO archive, BIO15; same terms | Same | Sample BIO15 and confirm percentage scaling; not fractional soil saturation | Null + disclose |
| V2 | `bio16_wettest_quarter_precip_mm` | Wettest-quarter precipitation normal, mm/quarter; nonnegative | Same BIO archive, BIO16; same terms | Same | Sample BIO16, not rolling last-72h rainfall | Null + disclose |
| V2 | `bio17_driest_quarter_precip_mm` | Driest-quarter precipitation normal, mm/quarter; nonnegative | Same BIO archive, BIO17; same terms | Same | Sample BIO17; not current forecast | Null + disclose |
| V2 | `elevation_m` | −500–9000 metres above sea level | WorldClim 2.1 SRTM-derived elevation, exact elevation archive above; same WorldClim terms | 30 arc-second (~1 km); source observation epoch not given in handoff | Sample original reference grid; verify vertical units/datum and training sampling convention. Do not substitute a 30 m DEM | Null + disclose |
| V2 | `slope_degrees` | 0–90 degrees, derived from that elevation grid | Derived from same WorldClim elevation; retain attribution/terms | ~1 km; derived date/algorithm absent | **Need teammate derivation code:** gradient method, CRS/geodesic distance treatment, edge/nodata handling and smoothing. A generic GDAL slope is not proven compatible | Null + disclose |
| V2 | `aspect_sin` | −1–1, sine of aspect azimuth; undefined on flat/near-flat cells | Same derived terrain | ~1 km | Need azimuth convention, radians conversion, flat threshold and algorithm. Raw aspect degrees are excluded from the model | Null when undefined/unavailable + disclose |
| V2 | `aspect_cos` | −1–1, cosine of the same aspect azimuth | Same derived terrain | ~1 km | Same; preserve paired missingness where aspect is undefined | Null + disclose |

Every key must still be present. V2's helper and teammate instructions allow all continuous fields to be null; its example API schema is stricter. Existing integration follows the helper/instructions and uses the saved pipeline, with `imputed_fields` in results. No WorldCover imputation is exposed despite a categorical imputer existing in the pipeline, because both supplied API/helper contracts require a supported class.

## Pilot and reproducibility gate

Use a small Shillong-area pilot, provisionally longitude 91.55–91.65 / latitude 25.25–25.35; these bounds are a proposed engineering test area, not verified model coverage. Test three interior points plus each raster boundary and nodata location. Obtain a teammate-approved extraction manifest specifying product URLs/versions, checksums, units/scales, depth/statistics, sampling and terrain algorithms before declaring real inputs compatible. Prefer source-clipped local files outside public assets; respect WorldClim restrictions and do not distribute its raw or derived values without permission.

Once compatibility and access are established, implement a shared FastAPI extraction service separately from inference. Its response must contain coordinates, selected model version, dataset/file hashes, CRS, pixel/grid location, value, source/date/resolution, scale applied, evidence type and unavailable reason per field. Inspection must precede an explicit inference action. Persist this extraction provenance with the assessment so a later dataset update cannot silently change history.

Tests must exercise actual raster CRS transforms, pixel edges, out-of-coverage points, masks/nodata and unit conversions—not just mock dictionaries. Reproduce teammate example extraction where the input coordinate/source pixels are supplied, then compare the saved helper outputs. Keep all data-unavailable states visible. Missing mandatory data blocks inference; never automatically switch to demo, another model, zeros or a different source.

## Demonstration versus real assessment

Current browser tests exercise a V1 handoff example and deliberate V2 null imputation, clearly named as tests, not a real location-derived assessment. They establish inference integration only. A future sample mode must be opt-in, labelled simulated/illustrative, and must not claim that a real raster was sampled at the clicked coordinates. Do not silently attach handoff example values to arbitrary locations. The existing demonstration data and manual model form remain usable while extraction is blocked.

## Outstanding prerequisites

1. Apply the proposed provider-domain settings and retry fresh connections; current attempts fetched no remote data.
2. Obtain the teammate's training-time extraction script/source manifest, especially SOC and terrain definitions. This asks for extraction provenance, not retraining or training ownership.
3. Acquire and verify a lawful local pilot bundle, then implement and validate the real extraction path. Until then, do not claim a completed location-based assessment workflow.
