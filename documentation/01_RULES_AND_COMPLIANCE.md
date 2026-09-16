# ResQ — Official Rules & Compliance Standards
**Project:** ResQ — Responsive Emergency Systems Intelligence  
**Challenge:** IEEE Response Quest Challenge 2026  
**Document Code:** `RESQ-DOC-01`  
**Status:** Mandatory Governance Document  

---

## 1. Executive Summary & Purpose
This document consolidates all mandatory technical rules, operational guidelines, design standards, and competition evaluation criteria for the ResQ platform. Every contributor, developer, and automated agent must strictly adhere to these rules throughout development, testing, and submission.

---

## 2. IEEE Response Quest Core Sub-Problems
The platform architecture must directly solve the six core sub-problems identified by the IEEE Response Quest Challenge committee:

1. **Access:** Locating and retrieving fragmented, real-time and static disaster-related data (weather, satellite, traffic, hospital capabilities, cell infrastructure).
2. **Storage:** Organizing and persisting heterogeneous emergency data for instant retrieval with strict UTC timestamps.
3. **Integration:** Aligning and fusing disparate data streams (civilian chat, live sensor/GPS, satellite feeds, maps) into a unified operational picture.
4. **User Interface:** Delivering an intuitive, single-screen visualization for high-density information without cognitive overload.
5. **Decision-Making:** Enabling rapid, informed actions focused specifically on **public protection** and the **safety of disaster responders**.
6. **Modeling:** Using data to simulate, predict, and forecast disaster scenarios, hazards, and response outcomes.

---

## 3. Mandatory IEEE Technical Deliverables ("Must Haves")

### 3.1 Platform Accessibility & Portability
- **Browser Compatibility:** Must run without friction on standard internet browsers:
  - Google Chrome
  - Microsoft Edge
  - Apple Safari
  - Mozilla Firefox
- **Zero-Installation:** All components (Civilian, Dispatcher, Responder) must run in standard browsers without requiring software installation or plugins.
- **Cross-Device Responsiveness:** Must fluidly scale across **Desktop, Tablet, and Mobile Phone** form factors.
- **Zero-Training Usability:** The interface must be immediately intuitive. A panicked civilian must be able to report an incident in under 60 seconds; a dispatcher or responder must understand current state at a glance.

### 3.2 User-Selected Region Filtering (Mandatory Requirement)
- The system **must** provide an interactive region selector enabling users to display and filter data across:
  1. **Community level** (e.g., Independence Layout, New Haven, Enugu Urban)
  2. **State / Regional level** (e.g., Enugu State, Lagos State)
  3. **Country level** (e.g., Nigeria)
- Switching region filters must dynamically scope map pins, weather cards, infrastructure overlays, and incident statistics.

### 3.3 Critical Infrastructure & Relationship to Disaster
- The GIS interface **must** display critical infrastructure assets and their spatial relationship to active incidents:
  - **Hospitals & Clinics:** Annotated with emergency capabilities (trauma, burn, general, pediatric) and 24/7 status.
  - **Nursing Homes & Vulnerable Care Centers.**
  - **Power Infrastructure:** Power stations and substations (NERC dataset).
  - **Telecommunications:** Cell towers (OpenCelliD dataset) and radio towers.
  - **Transportation Networks:** Major arterial roads, expressways, bridges, and rail lines.
- The interface must clearly indicate when an infrastructure asset is impacted or threatened (e.g., flooded road segments, power cut zones).

### 3.4 Real-Time Meteorological & Weather Hazard Warnings
- The platform **must** ingest and visualize current weather conditions and precipitation in near-real-time.
- The display must explicitly highlight responder-critical operational alerts:
  - Thunderstorm & lightning warnings
  - Flash flood & heavy precipitation alerts
  - Wind speed & directional warnings (crucial for structural collapse and fire spread)
  - Extreme heat / visibility / fog warnings
  - Operational impact assessment: stating clearly whether weather is escalating or hindering rescue operations.

### 3.5 Operational Cost Efficiency Rule
- The platform must be engineered for **maximum data currency at minimum hosting and operating cost**.
- Prefer open-source geospatial tools (Leaflet, OpenStreetMap), serverless/containerized lightweight backends (Flask, Python), free/open API tiers, and efficient caching over expensive enterprise software suites.

---

## 4. High-Value Judging Differentiators (Bonus Scoring Criteria)
To achieve maximum score in IEEE Phase 2 and Phase 3 evaluations, ResQ must actively incorporate the following bonus criteria:

1. **Impacted Population Calculations:** Dynamically calculate the estimated number of individuals impacted by an incident/disaster event and their geospatial centroid.
2. **Identification of Trapped Individuals:** Highlight individuals unable to self-evacuate using civilian natural language chat inputs and GPS coordinates.
3. **Escalation Tracking:** Every active incident card must show an escalation status: `Escalating`, `Steady`, or `De-escalating / Contained`.
4. **Infrastructure Service Outage Detection:**
   - Areas without electrical power
   - Areas with degraded or zero cell service
   - Roads/corridors that are impassable or submerged
5. **Dynamic Evacuation & Route Recommender:** Suggest safest evacuation corridors avoiding active hazards and flooded zones.

---

## 5. ResQ Brand Identity & UI Design Rules

### 5.1 Color System & Distribution Rules
Adhere strictly to the 50/30/15/5 color formula:

| Token | Hex | Target % | Semantic Usage |
|---|---|---|---|
| **ResQ Teal** | `#0D6E6E` | 50% (Primary) | Trust, life, authority. Base map controls, primary buttons, safe routes, logo mark. |
| **ResQ Chalk** | `#F7F5F0` | 30% (Surfaces) | Warm off-white reducing eye strain under stress. Card surfaces, input backgrounds. |
| **ResQ Ink** | `#1A1A1A` | 15% (Text / Base) | High-contrast body text, data labels, dark mode command base surface. |
| **ResQ Amber** | `#F0920A` | 5% (Alert Only) | **Strictly never decorative.** Appears ONLY for urgent states: SOS button, high-severity triage, hazard flags, blocked route dashes. |
| **Deep Purple** | `#3C3489` | Accent | Dispatcher interface badge / node accent. |
| **Coral** | `#993C1D` | Accent | Responder mobile interface badge / node accent. |
| **Neutral Grey** | `#2C2C2A` / `#4A4A48` | UI Chrome | Borders, dividers, data source pills, inactive connectors. |

### 5.2 Typography Rules
- **Primary Typeface:** `Inter` (Fallback: `DM Sans`, `Plus Jakarta Sans`, system sans-serif).
- **Permitted Weights:** **400 (Regular) and 500 (Medium) ONLY.**
- **Strict Prohibition:** **Do NOT use bold weights (600, 700, 800) or ALL-CAPS in body prose.** Typography must remain calm, precise, and readable under acute stress.
- **Minimum Font Size:** 12px for micro-labels/captions; 14–16px for body/inputs.

### 5.3 Iconography & Map Markings
- **Icon Library:** Tabler Icons or Lucide (clean, open-source outline stroke icons, 1.5px stroke at 24px).
- **Prohibited Symbols:**
  - Strictly **NO Red Cross or Red Crescent** (violates international humanitarian convention regulations). Use an outlined teal cross for hospitals.
  - Strictly **NO flashing sirens, pulsing red warnings, or alarming decorative animations** that induce bystander or responder panic.
- **Map Marker Standard:**
  - *Incidents:* Amber circle with white category glyph.
  - *Responders:* Teal circle with directional heading indicator.
  - *Hospitals:* Outlined teal cross marker with capability tag.
  - *Hazard Zones:* Amber polygon fill with 30% opacity.
  - *Blocked Roads:* Amber dashed line (`8, 8`).
  - *Optimal Route:* Solid teal polyline.

---

## 6. Strategic Framing & Clinical Protocol Rules

### 6.1 The "Civilian-as-Sensor" Framing
- **The Civilian Interface is the Ingestion Mechanism:** It exists to comfort, guide, and extract structured data from untrained bystanders.
- **The Responder & Dispatcher Tools are the Product:** IEEE judges evaluate responder decision support. Frame all AI conversations around the structured telemetry they yield for the first responder.

### 6.2 Clinical & Medical Safety Bounds
- AI first aid guidance must be strictly constrained to validated **World Health Organization (WHO)** and **Nigerian Red Cross** first aid protocols.
- The AI must explicitly declare itself as emergency bystander guidance, not a certified medical diagnosis.
- Instructions must be simple, sequential, and step-by-step (e.g., recovery position, direct wound pressure, burn cooling, snakebite immobilization).

### 6.3 Responsible Data Handling & NDPA 2023 Compliance
- **Zero Mandatory Authentication for Civilians:** Bystanders must never be blocked by login walls, sign-up forms, or password requirements during an emergency.
- **Ephemeral Incident Tracking:** GPS location is collected strictly for the duration of the active emergency response.
- **Voluntary Computer Vision:** Photo uploads for hazard assessment must be opt-in with transparent notification.
- **Encryption:** All data in transit must move over secure protocols (`HTTPS`, `WSS`).

---

## 7. Synthetic Data & Testing Rule
- To enable seamless judge evaluation without requiring real-world casualties, the system **must include a Synthetic Data Injection Tool**.
- Judges must be able to trigger simulated road traffic collisions, flash floods, and mass-casualty triage sequences with one click to observe end-to-end telemetry propagation.

