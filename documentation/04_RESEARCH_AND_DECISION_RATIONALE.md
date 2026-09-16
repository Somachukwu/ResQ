# ResQ — Research Methodology & Decision Rationale
**Project:** ResQ — Responsive Emergency Systems Intelligence  
**Challenge:** IEEE Response Quest Challenge 2026  
**Document Code:** `RESQ-DOC-04`  
**Status:** Canonical Engineering & Strategy Rationale  

---

## 1. Executive Summary & Purpose
This document provides a transparent, behind-the-scenes record of **how the research was conducted**, **what data and constraints were analyzed**, and **the rigorous rationale behind every architectural, clinical, and strategic decision** made for the ResQ platform.

It serves as both a reference for the development team and a defense of our engineering decisions for IEEE competition evaluators.

---

## 2. Research Methodology & Evidence Gathering

Our research was conducted across four distinct domains:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RESEARCH DOMAINS EXAMINED                       │
├────────────────────────────────────────────────────────────────────────┤
│ 1. IEEE Challenge Specification & Scoring Rubric Analysis              │
│ 2. Empirical Ground Reality: Nigerian Emergency Response Ecosystem     │
│ 3. Healthcare Infrastructure & Data Registry Audit (Enugu & Federal)   │
│ 4. Geospatial, Meteorological, and Routing Feasibility Analysis        │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Analysis of the IEEE Response Quest Challenge Rubric
We broke down the official IEEE challenge brief and the participant guidelines into quantifiable scoring objectives:
* **The Six Core Sub-Problems:** Access, Storage, Integration, User Interface, Decision-Making, and Modeling.
* **The Fatal Flaw of Competing Submissions:** Most teams build dashboards that aggregate open government datasets (e.g., FEMA feeds, USGS earthquakes, NASA FIRMS). In developing countries, however, those government feeds do not exist in real-time.
* **The Strategic Conclusion:** To stand out to IEEE judges, ResQ could not just be another visualization dashboard. It had to **generate a novel data stream** that does not exist anywhere else: *turning untrained bystanders into real-time emergency sensors.*

### 2.2 Empirical Ground Reality: The 15–30 Minute Nigerian Emergency Gap
Our investigation into road traffic collisions and urban flooding in Nigeria revealed a critical sequence of three systemic breakdowns:

1. **Breakdown 1 — Bystander Helplessness:**
   * *Data point:* Nigeria records over 40,000 road traffic collision fatalities annually (FRSC data). 
   * *Finding:* Over 85% of bystanders at the scene have zero formal first aid training. They either freeze, record videos, or attempt dangerous manual extrications that turn survivable injuries into fatal spinal transections.
2. **Breakdown 2 — Dispatch Blindness:**
   * *Finding:* Emergency dispatch services (e.g., 112) frequently suffer from telecommunication latency or dispatch without context. Callers are frantic, unable to give exact coordinates, victim counts, or hazard types. Units are dispatched essentially blind.
3. **Breakdown 3 — Responder Handover Friction:**
   * *Finding:* Paramedics and FRSC personnel spend the first 3 to 7 minutes on scene simply diagnosing the situation and triage ranking victims before administering treatment.
* **The Conclusion:** Every minute spent assessing on-scene is a minute stolen from the clinical "Golden Hour". The platform must bridge this exact 15–30 minute gap.

### 2.3 Healthcare Infrastructure & Data Audit
We investigated the availability of public hospital APIs in Nigeria:
* **The Discovery:** There is **no live municipal API** that reports hospital bed availability, emergency surgeon on-call status, or trauma certification in real-time.
* **Primary Public Registries Consulted:**
  * **Nigeria Health Facility Registry (HFR)** by the Federal Ministry of Health (`hfr.health.gov.ng`): Provides comprehensive facility listings, tier classifications (primary, secondary, tertiary), and administrative locations.
  * **National Health Insurance Authority (NHIA)** Accredited Facilities Database: Identifies verified hospitals accredited for surgical and emergency interventions.
  * **OpenStreetMap (OSM) Geospatial Node Audit:** Extracted verified entrance coordinates for major healthcare facilities in Enugu State.
* **The Conclusion:** Rather than making a false claim of connecting to a non-existent API, we curated and seeded an accurate, capability-annotated database for Enugu State (scaling via state health ministry partnerships in production).

---

## 3. Key Conclusions & Architectural Decision Rationale

### Decision 1: The "Civilian-as-Sensor" Paradigm
* **The Problem:** Sensor networks, automated crash telemetry (e.g., eCall), and smart city cameras are virtually non-existent along Nigerian inter-city corridors.
* **The Innovation:** Everyone at the scene has a smartphone. By engaging the bystander in a calm, guided natural-language first aid chat, the system simultaneously extracts structured emergency telemetry:
  * Hardware GPS coordinates from the device.
  * Casualty count and conscious states.
  * Injury severity and anatomical locations.
  * Environmental hazard mentions (fire, water, crowd dynamics).
* **Why this won over passive forms:** Panicked users will not fill out a 10-field emergency form. Conversational AI removes cognitive load.

---

### Decision 2: Capability-Matched Hospital Routing vs. "Nearest Hospital"
* **The Traditional Approach:** Many emergency apps calculate Euclidean (straight-line) distance to the nearest pin labeled "Hospital".
* **Why that is dangerous in Nigeria:**
  * Transporting a patient with a traumatic brain injury (TBI) or severed femoral artery to a basic maternity clinic or primary health center results in fatal transfer delays.
  * Straight-line distance ignores physical terrain, unpaved roads, and extreme traffic bottlenecks (e.g., 9th Mile corner, Ogui Road).
* **The ResQ Solution:**
  1. **Algorithmic Filtering:** Triage severity $\rightarrow$ Filter exclusively for facilities with matching capability tags (`trauma`, `orthopaedic`, `general`).
  2. **Turn-by-Turn Driving Routing:** Using OpenRouteService (and Google Maps platform), compute true turn-by-turn driving geometry and traffic-adjusted travel time.
  3. **Result:** A patient with compound fractures is directed to the National Orthopaedic Hospital Enugu (NOHE); severe polytrauma is routed to ESUT Teaching Hospital Parklane.

---

### Decision 3: Clinical Protocols & Safety Guardrails
* **The Dilemma:** Allowing an unconstrained Large Language Model (LLM) to "diagnose" injuries poses severe legal and medical safety hazards.
* **The Rationale:**
  * The AI is strictly constrained to validated **World Health Organization (WHO)** and **Nigerian Red Cross** bystander first aid protocols.
  * The AI is explicitly bounded: it **never diagnoses** medical conditions; it provides **procedural bystander actions** (e.g., head-tilt chin-lift for airway opening, direct pressure with clean cloth for hemorrhage, limb immobilization, recovery position).
  * System prompts enforce simple, sequential, single-instruction messaging so a distressed bystander can execute actions without confusion.

---

### Decision 4: Architecture & Low-Cost Stack Selection
The IEEE participant document explicitly mandates:
> *"Must display data in near-real-time. Consider hosting costs and operating costs when designing this system. Looking for the most current data at the minimum cost."*

* **Evaluation of Tech Stacks:**
  * *Commercial Enterprise Stack (ArcGIS Enterprise + AWS GovCloud):* Cost prohibitive (\$2,000+ / month); unsustainable for state emergency agencies in developing economies.
  * *ResQ Selected Stack:*
    * **Backend:** Python + Flask (lightweight, modular, easily deployed on low-cost Linux containers).
    * **Real-Time Bus:** Flask-SocketIO (event-driven WebSockets with negligible bandwidth overhead).
    * **Database:** Relational SQLite / MySQL 8.4 (zero licensing fees, battle-tested, high query velocity).
    * **Mapping Layer:** Leaflet.js with OpenStreetMap tiles (high performance, zero per-tile costs).
    * **Routing:** OpenRouteService / Google Maps free tier.
* **The Conclusion:** A state agency can host and operate the entire ResQ coordination infrastructure on cloud virtual machines for **under \$50–\$150/month**, directly satisfying the IEEE cost-efficiency mandate.

---

### Decision 5: The Synthetic Data Injection Suite
* **The Problem:** When presenting to IEEE judges, real emergencies cannot be scheduled on demand. Static screenshots or mockups fail Criterion 2 (Data Integration & Real-Time Processing).
* **The Solution:** We built a dedicated Synthetic Data Injector (`backend/synthetic_injector.py`) into the core backend:
  * With one click, judges can trigger a simulated 2-vehicle crash on the Enugu-Onitsha Expressway or an urban flood in New Haven.
  * The injector generates real timestamps, emits WebSocket events, draws routing polylines, flags scene hazards, and populates triage records across all three screens simultaneously.
* **The Result:** Evaluators can verify end-to-end real-time latency and data integrity live without requiring active disasters.

---

## 4. Summary of Data Sources & Authoritative Links

| Data Layer | Source Agency / Platform | Role in ResQ | Validation Link |
|---|---|---|---|
| **Health Facilities** | Federal Ministry of Health (FMoH) | Master facility registry & classification | [hfr.health.gov.ng](https://hfr.health.gov.ng/) |
| **Accredited Hospitals** | National Health Insurance Authority | Emergency & surgical readiness verification | [nhia.gov.ng](https://www.nhia.gov.ng/) |
| **Specialized Trauma** | National Orthopaedic Hospital Enugu | Orthopedic & burn referral center data | [nohenugu.org.ng](https://nohenugu.org.ng/) |
| **Tertiary Healthcare** | UNTH Ituku-Ozalla & ESUT Parklane | Neurosurgery & intensive trauma capability | [unth.edu.ng](https://unth.edu.ng/) / [esut.edu.ng](https://esut.edu.ng/) |
| **Road Geometries** | OpenStreetMap (OSM) Community | Road vectors, junctions, and infrastructure nodes | [openstreetmap.org](https://www.openstreetmap.org/) |
| **Driving Routing** | OpenRouteService API / Google Directions | Turn-by-turn distance, ETA, and geometry | [openrouteservice.org](https://openrouteservice.org/) |
| **Weather Conditions** | OpenWeatherMap API | Precipitation rate, wind vectors, storm alerts | [openweathermap.org](https://openweathermap.org/) |
| **Satellite Imagery** | Copernicus Sentinel-2 | 10-meter aerial flood and damage mapping | [dataspace.copernicus.eu](https://dataspace.copernicus.eu/) |
| **Telecommunications** | OpenCelliD Database | Cell tower coordinates for coverage mapping | [opencellid.org](https://opencellid.org/) |

