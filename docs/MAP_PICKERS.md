# Map selection in location-entry forms

Every editable point-coordinate form uses the same **Select coordinates on map** control:

- Citizen reports, alongside typed latitude/longitude and the existing GPS action.
- Monitoring locations, roads, villages/population cells and infrastructure, in creation and editing forms.
- Historical events and satellite-imagery records.
- Automatic model assessment coordinates.
- Report-first dispatch destination corrections.

Select the button to open a map, click to place a draft pin, then select **Use selected coordinates**. The existing fields are updated only on confirmation. **Cancel map selection** leaves all current fields intact, including previously captured GPS coordinates/accuracy. Manual entry remains available. Map-chosen citizen coordinates clear measured GPS accuracy instead of inheriting the accuracy of a different GPS position. Location descriptions remain user-entered. Monitoring-location records also offer a separate, reviewed place/terrain lookup described in `LOCATION_DETAILS.md`; map selection alone does not perform that lookup.

The map is mounted only when opened, so it receives a visible container size. Scroll-wheel zoom is disabled to avoid changing zoom while scrolling a form. Existing coordinates centre the map; otherwise it opens on the regional reference area without inserting default coordinates into the form. Online tiles are attempted through the existing provider mechanism; unavailable tiles fall back to the bundled attributed geographic reference. That reference is approximate context, not street navigation. Longitudes from map clicks are wrapped to the valid geographic range.

Where a form requires a **saved monitoring-location record**, use **Select saved location on map** instead:

- Weather location selection.
- Manual model-observation location association.
- Monitoring-location-based general response planning.
- Alert creation/editing location association.

Only saved records with valid coordinates appear as selectable markers. Click a marker and confirm **Use selected saved location**. Clicking blank map space never chooses a nearest record, creates a monitoring record, or changes an association. The dropdown remains available for keyboard selection. If no saved locations exist, the map action is disabled with an explanation. This requirement does not apply to report-first dispatch, which continues to use incident coordinates directly.

For dispatch, confirming a map correction clears destination/team confirmations and retains the review note. The existing correction-reason and explicit destination/team confirmation rules remain enforced on the backend. Map selection itself never submits a report, saves a record, runs a model, publishes an alert or assigns a team.

Validation: `docs/evidence/20261113T172700Z/` records 58 passed Python tests and 31 passed browser tests, plus build, translation and configuration checks. New browser cases cover citizen confirm/cancel with GPS accuracy clearing and persistence; record creation and edit cancellation; all six record-coordinate form types; saved-record selection without creation; assessment selection without automatic extraction; and dispatch correction/reconfirmation with original coordinates preserved. The earlier three focused picker cases also passed before the final full run. Models, environmental rasters and application records are not replaced or reseeded.
