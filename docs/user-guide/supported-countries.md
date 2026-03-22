# Supported Countries

## v0.1 Country Coverage

The current country list in v0.1 is:

- Nigeria (`NGA`)
- Ghana (`GHA`)
- Côte d'Ivoire (`CIV`)
- Senegal (`SEN`)
- Cameroon (`CMR`)

If you use a country outside this list, AIS returns a corridor-not-supported error.

## Supported Corridors

The seeded and tested corridor coverage in v0.1 is:

- `GHA -> NGA`
- `CMR -> NGA`

These are the corridors currently loaded with tariff data and used in the end-to-end examples and test coverage.

## What “Supported” Means

When a country or corridor is supported, that means AIS has the necessary legal and operational data loaded for decision support, including:

- product-specific rule data
- tariff data for the corridor
- status-aware decision logic
- evidence and audit support

In practice, you should treat a corridor as truly usable only when the relevant corridor data is actually loaded.

## What Is NOT Supported In v0.1

v0.1 does not support:

- other African countries outside the five-country list above
- HS8 or HS10 computation as a decision layer
  AIS accepts longer input codes, but truncates them to HS6 for computation.
- real-time legal update feeds
- automatic legal monitoring across all African jurisdictions
- full-continent tariff and corridor coverage

## Important Limitation

The country list and the corridor data are not the same thing.

- A country may be in the supported country list
- but that does not automatically mean every corridor involving that country has full tariff and operational data loaded

For that reason, always verify:

- the country is in scope
- the corridor data exists
- the tariff and status outputs are not provisional or missing

## Planned Expansions

Planned future expansion areas include:

- more AfCFTA member states
- more corridor pairs
- broader tariff coverage
- deeper operational status coverage
- richer evidence and audit coverage
- better update cadence for legal and schedule data

Until those expansions are loaded, use AIS as a scoped v0.1 decision-support engine rather than a full-Africa production clearance platform.
