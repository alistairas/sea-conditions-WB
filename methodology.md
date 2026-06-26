# Whitley Bay Multi-Source Sea Temperature Record

### Bringing together swimmers, satellites and history to understand Whitley Bay's changing sea temperature.

# Apple Watch Water Temperature Methodology

**Version:** 0.1

---

## Purpose

This document describes the methodology used to process Apple Watch water temperature observations collected during sea swims at Whitley Bay.

The aim is to derive a representative estimate of seawater temperature for each swim session using a transparent, reproducible methodology.

This methodology supports the Whitley Bay Multi-Source Sea Temperature Record, which combines swimmer observations, satellite Earth observation and historical local records to improve understanding of coastal sea temperature at Whitley Bay.

---

## Data source

Water temperature observations are extracted from Apple Health workout data recorded by an Apple Watch during open-water swims.

---

## Processing workflow

### 1. Extract observations

Water temperature observations are extracted into a CSV dataset containing:

- Timestamp
- Water temperature (°C)

---

### 2. Identify swim sessions

Consecutive observations are grouped into individual swim sessions.

A new session begins whenever there is a gap of more than **30 minutes** between consecutive observations.

---

### 3. Estimate representative water temperature

The representative water temperature for each swim session is estimated from the **stable temperature plateau** observed after the Apple Watch has equilibrated with the surrounding seawater.

The methodology identifies the period during which recorded temperatures remain relatively stable, representing the point at which the sensor is considered to have reached thermal equilibrium with the surrounding water.

The representative temperature for the session is derived from the **median temperature** observed during this stable period.

Where a stable plateau cannot be identified with sufficient confidence, the session is flagged for review.

---

## Data quality

Apple Watch water temperature observations are affected by several factors, including:

- body heat prior to entering the water
- gradual sensor equilibration
- wetsuit coverage
- post-swim activity
- variable recording frequency

For this reason, raw observations are not interpreted directly. Instead, representative temperatures are derived using the methodology described above.

---

## Validation

The processing methodology will be evaluated by comparison with independent observations, including:

- Copernicus Marine Service sea surface temperature (SST)
- Historical local water temperature records

The objective is not to reproduce either dataset exactly, but to understand how swimmer-collected observations relate to other methods of measuring coastal sea temperature.

---

## Guiding principles

The project follows five principles:

- **Transparent** – every published value can be traced back to the underlying observations.
- **Reproducible** – processing is automated and documented.
- **Evidence-led** – methodological decisions are informed by analysis rather than assumption.
- **Conservative** – uncertain observations are identified rather than overstated.
- **Open** – datasets and methodology are shared wherever privacy allows.

---

## Status

This document describes the current processing methodology.

As additional observations become available and validation work progresses, the implementation used to identify the stable temperature plateau may be refined. Any methodological changes will be documented through version control and accompanied by an updated methodology version.

---

## Scope

This project is intended as a transparent citizen science initiative rather than an official oceanographic monitoring programme.

Its purpose is to explore how swimmer-collected observations can complement satellite Earth observation and historical local records, while making both the data and the methodology openly available for others to review, reproduce and improve.

---

## Project

**Whitley Bay Multi-Source Sea Temperature Record**

*Bringing together swimmers, satellites and history to understand Whitley Bay's changing sea temperature.*
