# ResQ — Responsive Emergency Systems Intelligence

> **IEEE Response Quest Challenge 2026** · Enugu State, Nigeria · $100,000 Prize Track  
> *Every second between emergency detection and trauma admission decides human survival.*

📖 **[Read the Full Technical Dossier & Judges Submission Manual (PROJECT_DOCUMENTATION.md)](PROJECT_DOCUMENTATION.md)**

---

## 🚀 Overview

**ResQ** is a next-generation pre-hospital emergency response orchestration platform engineered for Enugu State, Nigeria. It bridges the critical operational gap between:
1. **Civilians & Bystanders** at accident scenes facing shock, network instability, and fear.
2. **Emergency Dispatchers** triaging calls with real-time GIS layers, severity indexing, and responder allocation.
3. **Field Responders (Ambulance / FRSC)** receiving ultra-legible 10-second mission briefs with hazard alerts and pre-routed trauma hospital handoffs.

---

## 📁 System Architecture

```
ResQ/
├── frontend/                     # Production Unified Frontend (Vanilla HTML5 / CSS3 / ES6)
│   ├── index.html                # Central Portal Navigation Hub (Civilian / Dispatcher / Responder)
│   ├── templates/
│   │   ├── civilian/
│   │   │   └── index.html        # One-Tap SOS, offline first-aid, humane reassurance
│   │   ├── dispatcher/
│   │   │   └── dashboard.html    # Leaflet GIS command center, RSI queue, fleet strip, split comms
│   │   └── responder/
│   │       └── scene_brief.html  # Heads-up mission brief, ticking ETA, safety alerts, ack flow
│   └── static/
│       ├── css/
│       │   ├── resq.css          # Design tokens (Teal #0D6E6E, Amber #F0920A, Inter typography)
│       │   ├── civilian.css      # Stress-calming layout, high-contrast SOS button
│       │   ├── dispatcher.css    # Multi-pane tactical GIS command center layout
│       │   └── responder.css     # Arm's-length mobile cards, daylight-legible contrast
│       └── js/
│           ├── resq-theme.js     # Light/Dark mode switcher with localStorage persistence
│           ├── resq-protocols.js # Clinical first-aid protocols (offline indexed)
│           ├── civilian.js       # Offline caching, geolocation watcher, audio cues
│           ├── dispatcher.js     # Leaflet map manager, RSI sorting, 1-tap dispatch modal
│           └── responder.js      # GPS telemetry heartbeat, arrival countdown, ack sync
├── app.py                        # Flask Backend Application & Routing
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment configuration template
└── README.md                     # Documentation
```

---

## 🎨 Three Coordinated Operational Portals

### 1. Civilian Safety Portal (`/civilian`)
* **Tone**: Calm, authoritative, reassuring (*"You are not alone. We are with you."*).
* **Key Features**:
  * Massive high-visibility SOS trigger.
  * Works offline — emergency first-aid protocols cached on device.
  * Silent background GPS streaming and automated victim status reporting.
  * Audio tone cues and real-time arrival countdown.

### 2. Tactical GIS Dispatch Command (`/dispatcher`)
* **Tone**: High-density tactical awareness.
* **Key Features**:
  * Interactive Leaflet GIS map with Enugu coordinates (Enugu–Onitsha Expressway, Parklane, UNTH, Orthopaedic).
  * Layer toggles: Live Incidents, Responder Units, Hospital Capabilities, Flood Blackspots, Satellite.
  * **RSI (ResQ Severity Index)** queue automatically prioritizing critical life threats (RSI ≥ 4.0).
  * 1-Tap dispatch assignment modal with nearest capability-matched unit.
  * Split communications console (Civilian bystander channel + Responder fleet net).

### 3. First Responder Heads-Up Brief (`/responder`)
* **Tone**: Sunlight-legible, arm's-length readable, zero clutter.
* **Key Features**:
  * **Ticking Arrival Countdown** (`Arriving in 12:04 min`).
  * **02 Victims Overview Badge** with prominent `CRITICAL` triage tag.
  * **Hazard & Safety Alerts** (e.g., fuel spills, traffic closures).
  * **Interactive Brief Acknowledgement** (`Acknowledge brief →` toggles to confirmed status).
  * **Pre-Routed Level-1 Destination** with clinical rationale (overriding nearest clinic if neurosurgery/transfusion required).
  * Turn-by-turn navigation link and live dispatch radio channel indicator.

---

## 🌓 Universal Light & Dark Mode
All pages feature a coordinated Light / Dark mode toggle switch with smooth token transitions, persistent via `localStorage`, defaulting to Dark Mode for high-contrast tactical use.

---

## 🌐 Live Hosted Web Platform

ResQ is deployed and fully accessible online with zero local setup or installation required:

* **Central Navigation Hub:** [https://somachukwu.github.io/ResQ/](https://somachukwu.github.io/ResQ/)
* **Civilian Safety Portal:** [https://somachukwu.github.io/ResQ/civilian/](https://somachukwu.github.io/ResQ/civilian/)
* **Dispatcher Command Center:** [https://somachukwu.github.io/ResQ/dispatcher/](https://somachukwu.github.io/ResQ/dispatcher/)
* **Field Responder Heads Up HUD:** [https://somachukwu.github.io/ResQ/responder/](https://somachukwu.github.io/ResQ/responder/)
* **Cloud API Gateway:** `https://resq-backend-oj6j.onrender.com`

---

## 🏆 IEEE Response Quest Challenge 2026 Standards
* **Zero Framework Bloat**: Pure Vanilla HTML5/CSS3/ES6 frontend ensures instant mobile load times even on 2G/3G connections in Enugu suburban corridors.
* **Clinical Accuracy**: Triage and hospital routing strictly align with trauma surgery, ICU bed availability, and blood bank requirements.
