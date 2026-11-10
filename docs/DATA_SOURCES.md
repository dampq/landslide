# Data provenance and imports

`manage.py seed-demo` inserts labelled synthetic examples across the eight North Eastern states. It is repeatable without overwriting edited records. Sample place coordinates refer to real towns, but roads, infrastructure, events, population and weather values are invented demonstration data, not surveyed facts. Sensors are generated only when an official runs the simulator.

## Public sources

The History & imagery portal lists GSI Bhukosh, NRSC Bhuvan, NASA GPM IMERG, NASA SRTM, NASA SMAP, OpenStreetMap, WorldPop and Copernicus. They are **source references, not claims that all feeds are integrated**. Downloads, registration, licenses, formats and public availability vary. Restricted government resources are not required.

- Open-Meteo forecast ingestion is implemented. Rainfall for past hours is provider-modelled data, not gauge observations. Forecast/cache timestamps, staleness and attribution are shown. If the provider cannot be reached, existing cache remains and a clear error is returned.
- Leaflet uses OpenStreetMap base tiles with attribution. The app does not bulk cache those tiles.
- Historical inventories, elevation/slope, soil moisture and road/infrastructure records can be entered manually or imported after lawful public download and preparation. This app does not derive slope from DEM rasters or convert soil-moisture conventions automatically.
- WorldPop-style population cell centres and counts can be imported as population records. Supply dataset year, cell resolution, source and license. Exposure sums counts whose centres fall inside a PostGIS geodesic radius; boundary cells are not area-weighted. It is an approximate planning estimate, not a count of people in a predicted landslide footprint. Do not import overlapping village totals and grid cells into the same analysis dataset, as that would double-count residents.
- Copernicus Browser supports external Sentinel-1/2 imagery exploration. Store public imagery references and acquisition descriptions as records. Satellite processing, subscriptions and image classification are optional, not fabricated.

## Import format

Administrators import JSON objects with an `items` array or GeoJSON Point FeatureCollections, up to 500 records per request. Supported collections: locations, roads, villages (population points), infrastructure, history and satellite. Road geometry in this student version is a representative point with a route description, not a road-routing network.

Every record requires `source` (nonempty text) and `simulated` (boolean). Exact duplicate record content imports idempotently; changed records create new entries, so review updates rather than repeatedly importing revised population totals. Invalid batches are rejected atomically. Exported CSVs include source and simulation fields and neutralise spreadsheet formula prefixes.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [91.582, 25.297] },
      "properties": {
        "name": "Sample population cell",
        "population": 120,
        "year": 2020,
        "resolutionM": 100,
        "license": "Synthetic example",
        "source": "Ashtaraksha synthetic demonstration",
        "simulated": true
      }
    }
  ]
}
```

To import real data, replace all example values and provenance, verify the source's license, and set `simulated` to false only for actual sourced observations. Use the API schema at `/docs` for endpoint definitions. Do not publish user reports as authoritative historical events without review.
