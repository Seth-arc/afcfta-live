# Supported Countries

## v0.1 Country Coverage

The current country list in v0.1 is:

- Nigeria (`NGA`)
- Ghana (`GHA`)
- Cote d'Ivoire (`CIV`)
- Senegal (`SEN`)
- Cameroon (`CMR`)

If you use a country outside this list, AIS returns a corridor-not-supported error.

## Published Active Corridor Profiles

The seeded `corridor_profile` surface currently published through the intelligence
API is intentionally narrower than the full locked acceptance corpus. As of
March 30, 2026, the active published corridor-profile pairs are:

- `GHA -> NGA`
- `CMR -> NGA`
- `CIV -> NGA`
- `SEN -> NGA`
- `GHA -> CMR`

`GET /api/v1/intelligence/corridors/{exporter}/{importer}` should be treated as
supported only for those five directed pairs.

## Acceptance Coverage Is Broader Than Published Profiles

The locked golden assessment slice covers 6 directed corridors, including
synthetic test-seeded acceptance scenarios such as `CIV -> SEN` and `NGA -> GHA`.
Those cases validate assessment behavior, but they are not the same thing as
published active `corridor_profile` rows.

That distinction matters:

- a country can be in scope for v0.1
- a corridor can be valid for deterministic assessment tests
- but the intelligence profile endpoint can still return `404` if no active
  corridor profile has been seeded for that exact pair

## What "Supported" Means

When a country or corridor is supported for operational use, AIS has the
necessary legal and operational data loaded for that surface, including:

- product-specific rule data
- tariff data for the corridor
- status-aware decision logic
- evidence and audit support
- an active corridor profile when using the intelligence profile endpoint

Always verify:

- the country is in scope
- the corridor data exists for the API surface you are calling
- the tariff and status outputs are not provisional or missing

## What Is Not Supported In v0.1

v0.1 does not support:

- countries outside the five-country list above
- HS8 or HS10 computation as a decision layer
- real-time legal update feeds
- automatic legal monitoring across all African jurisdictions
- full-continent tariff and corridor-profile coverage

AIS accepts longer product codes on input, but truncates them to HS6 for computation.
