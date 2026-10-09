# ResQ: Responsive Emergency Systems Intelligence
## Official Competition Functional Dossier & Judges Evaluation Manual
**IEEE Response Quest Challenge 2026 · Disaster & Crisis Emergency Intelligence Track**  
**Geographical Deployment:** Enugu State, Federal Republic of Nigeria  
**Live Hosted Web Platform:** https://somachukwu.github.io/ResQ/  
**Official Cloud API Gateway:** https://resq-backend-oj6j.onrender.com  

---

## 1. Executive Summary & Mission Statement

In emergency trauma care, the Golden Hour is the decisive window between acute injury and definitive surgical treatment. In advanced healthcare systems, centralized 911 dispatch, unified GIS tracking, and automated trauma registries minimize mortality during this critical period.

In developing regions, specifically across highway corridors and urban centers in Nigeria, this safety net is severely fragmented:
1. **The Communication Void:** Panicked citizens at crash scenes, structural collapses, or flood hazards have no reliable universal triage dispatch number. They face call drops, network volatility, and cognitive paralysis.
2. **The Intelligence Deficit:** Dispatchers rely on frantic, unstructured verbal descriptions without geographic coordinates, physiological telemetry, or environmental hazard awareness.
3. **The Transit Penalty:** Emergency medical responders and road safety crews deploy blindly into congested routes without clinical briefings, frequently transporting neurotrauma victims to basic clinics rather than equipped tertiary trauma centers.

**ResQ (Responsive Emergency Systems Intelligence)** is a specialized pre hospital emergency response orchestration platform engineered to eliminate this fatal operational latency. Built specifically for the **IEEE Response Quest Challenge 2026**, ResQ introduces a vital operational paradigm:

> **The ResQ Core Thesis:** Rather than relying exclusively on sparse, delayed static datasets, ResQ transforms untrained scene bystanders into structured, real time emergency sensor nodes using Multimodal Artificial Intelligence. The platform dynamically fuses citizen observations with hydro meteorological risk models, highway crash blackspot analytics, and capability matched hospital routing, delivering instant clinical guidance, tactical dispatch command, and heads up responder briefings.

---

## 2. Alignment with IEEE Response Quest Challenge Core Problems

The IEEE Response Quest Challenge specifies six critical functional requirements for crisis intelligence systems. ResQ addresses every requirement through dedicated functional capabilities:

| IEEE Challenge Requirement | ResQ Functional Capability | Operational Outcome |
|---|---|---|
| **1. Data Access** | Multi source live ingestion fusing citizen scene observations, browser geolocation coordinates, precipitation indices, and regional crash blackspot data. | Zero delay situational awareness without manual data entry. |
| **2. Data Storage** | Ephemeral, audited incident records anchoring every chat turn, hazard alert, telemetry stream, and responder state transition under a unique Incident UUID. | Tamper proof operational record complying with Nigeria Data Protection Act (NDPA 2023). |
| **3. Data Integration** | Real time event bus synchronizing citizen WebRTC audio, computer vision hazard flags, GPS position vectors, and hospital capability handoffs. | A synchronized Common Operational Picture shared across all three portals simultaneously. |
| **4. User Interface** | Three zero training web interfaces engineered specifically for user stress levels: Civilian Mobile PWA, Dispatcher GIS Command, and Responder HUD. | Instant legibility and zero operator error during high cognitive load events. |
| **5. Decision Making** | Automated triage prioritization (ResQ Severity Index 1.0 to 5.0), environmental hazard warnings, and capability matched ambulance allocation. | Objective triage sorting replacing subjective guesswork. |
| **6. Predictive Modeling** | Mathematical modeling encompassing hydro meteorological flood inundation and spatial highway corridor crash risk density. | Proactive hazard avoidance routing and optimal unit staging along hazardous corridors. |

---

## 3. Functional Architecture & System Ecosystem

ResQ operates as a real time operational ecosystem that links three distinct user roles into a single synchronized workflow:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              LIVE SENSORY INGESTION                                    │
│ • Bystander Voice / Text / Images          • Real Time Geolocation Telemetry           │
│ • Environmental Precipitation Data         • Highway Corridor Crash Blackspot History   │
│ • Topographic Elevation & Flood Basins     • Regional Hospital Capability Profiles     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        INTELLIGENCE & DECISION ENGINES                                 │
│ 1. ResQ Severity Index (RSI 1.0 to 5.0): Deterministic Physiological Triage Ranking    │
│ 2. Multimodal AI Clinical Triage: Multi Turn Symptom Extraction & First Aid Guidance  │
│ 3. Spatial Corridor Crash Risk Index: Statistical Density Analysis on Transit Corridors│
│ 4. Flood Inundation & Culvert Impassability Analysis: Weather & Runoff Forecasting     │
│ 5. Golden Hour Trauma Routing: Survival Decay Optimization S(t) = S0 * exp(-lambda * t)│
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                       SYNCHRONIZED EVENT DISTRIBUTION BUS                              │
│       Real Time WebSocket Event Relay · WebRTC Browser Peer Connection Voice           │
└───────────────────┬───────────────────────────────┬────────────────────────────────────┘
                    │                               │
                    ▼                               ▼
     ┌─────────────────────────────┐  ┌─────────────────────────────┐
     │   CIVILIAN SAFETY PORTAL    │  │   DISPATCHER GIS COMMAND    │
     │ https://somachukwu.github.io│  │ https://somachukwu.github.io│
     │         /ResQ/civilian/     │  │        /ResQ/dispatcher/    │
     │ • High Visibility SOS Tap   │  │ • Tactical GIS Incident Map │
     │ • Multimodal AI Chat & Voice│  │ • Automated RSI Queue Sort  │
     │ • Two Phase Clinical Triage │  │ • One Tap Fleet Allocation  │
     │ • Offline First Aid Library │  │ • Dedicated Dual Comms Space│
     │ • Live Synchronized ETA     │  │ • Encrypted Voice Bridge    │
     └─────────────────────────────┘  └──────────────┬──────────────┘
                                                     │
                                                     ▼
                                      ┌─────────────────────────────┐
                                      │  RESPONDER HEADS UP HUD     │
                                      │ https://somachukwu.github.io│
                                      │        /ResQ/responder/     │
                                      │ • Ten Second Mission Brief  │
                                      │ • Ticking ETA Countdown     │
                                      │ • Critical Scene Hazards    │
                                      │ • Pre Routed Trauma Center  │
                                      │ • One Tap Acknowledgment    │
                                      └─────────────────────────────┘
```

---

## 4. The Three Operational Portals & Core Capabilities

ResQ provides three distinct portals accessible directly through any modern web browser without software installation:

### 4.1 Civilian Safety Portal
**URL:** `https://somachukwu.github.io/ResQ/civilian/`  
**Target Users:** Scene bystanders, crash victims, family members, community witnesses.  
**Functional Capabilities:**
* **One Tap High Visibility SOS Activation:** Instant emergency triggering with a single touch, immediately transmitting background GPS coordinates.
* **Multimodal AI Interactive Triage:** Supports natural text, spoken voice, and image uploads in standard English as well as Nigerian Pidgin (e.g., *"Person dey bleed heavy for head, moto scatter"*).
* **Two Phase Clinical Dialogue:** 
  * *Phase 1:* The assistant asks focused questions to ascertain critical demographics and wound specifics (victim gender, conscious state, bleeding severity).
  * *Phase 2:* Immediate delivery of concise, step by step World Health Organization (WHO) compliant first aid instructions.
* **Offline First Aid Protocol Library:** Emergency first aid advice remains instantly searchable on device even during network blackouts.
* **Synchronized Live ETA Counter:** A live ticking arrival countdown that automatically starts and synchronizes the moment the response crew confirms departure.
* **Encrypted WebRTC Voice Bridge:** Direct browser to browser voice link connecting the bystander to emergency dispatch with telephone line presence hum and connection chime.

### 4.2 Emergency Dispatch GIS Command Center
**URL:** `https://somachukwu.github.io/ResQ/dispatcher/`  
**Target Users:** Emergency operations center controllers, FRSC dispatchers, state disaster management coordinators.  
**Functional Capabilities:**
* **Tactical GIS Spatial Overview:** Interactive mapping displaying live incident pins color coded by severity, ambulance fleet locations, and monitored hospital facilities across Enugu State.
* **ResQ Severity Index Priority Queue:** Incidents are algorithmically ordered from Critical Red (RSI 4.0 to 5.0) down to Minor Green (RSI 1.0 to 1.9), ensuring life threatening cases receive immediate attention.
* **One Tap Rapid Fleet Allocation:** Dispatchers can assign the nearest available ambulance unit (such as AMB 01 or AMB 02) with a single click, automatically transmitting incident briefs to the field crew.
* **Dedicated Dual Net Communication Console:** A permanent multi channel communication window allowing the dispatcher to converse with the scene bystander on one channel and coordinate with the responding ambulance team on a separate tactical channel.
* **Automated Environmental Hazard Banner:** Alerts dispatchers immediately if fuel leaks, fires, downed power cables, or flood waters are identified at the scene.
* **Real Time Incident Telemetry Feed:** Displays live victim count, casualty demographics, anatomical injury sites, and medical guidance given to bystanders.

### 4.3 Field Responder Heads Up HUD Portal
**URL:** `https://somachukwu.github.io/ResQ/responder/`  
**Target Users:** Paramedic crews, ambulance drivers, FRSC rescue patrol officers.  
**Functional Capabilities:**
* **Ten Second Mission Brief:** High contrast, sunlight readable mobile display highlighting only critical operational data: incident location, casualty count, triage tag, and injury type.
* **Pre Arrival Scene Hazard Warnings:** Clear warning badges alerting crews to scene risks (such as *"Flammable Fuel Spill"* or *"Downed Electric Cable"*) before arriving on scene.
* **One Tap Departure & Arrival Confirmation:** Field crews confirm departure with one tap, instantly updating the command console and starting the live arrival countdown on the civilian device.
* **Pre Routed Tertiary Trauma Center Selection:** Automatically identifies and pre selects the optimal regional trauma hospital (such as ESUTH Parklane Hospital or UNTH Ituku Ozalla) matched to the patient trauma profile.
* **GPS Route Orientation:** Direct navigation links to navigate emergency vehicles swiftly around congested or impassable highway corridors.

---

## 5. Multimodal Clinical AI Triage & Safety Boundaries

### 5.1 Conversational Triage Architecture
The ResQ clinical triage engine processes bystander communication using multimodal artificial intelligence designed specifically for emergency conversations.

```
Citizen Scene Input (Voice / Text / Scene Image)
                  │
                  ▼
       [ Multimodal AI Parser ]
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
[ Clinical Telemetry ]   [ Scene Hazards ]
• Casualties Count       • Fuel Spill
• Trauma Severity        • Active Fire
• Anatomical Injury      • Rising Water
• Victim Demographics    • Power Lines
        │                   │
        ▼                   ▼
[ Two Phase Response Engine ]
  • Phase 1: Clarify Demographics & Wound Details
  • Phase 2: Actionable WHO First Aid Steps
```

### 5.2 Two Phase Inquiry Protocol
To eliminate robotic repetitive phrases and optimize bystander composure, ResQ enforces a structured two phase dialogue:
* **Phase 1 (Clarification):** When a report is submitted, the assistant immediately asks targeted clarifying questions:
  * *"Is the victim male or female?"*
  * *"Is the bleeding pulsing or soaking through clothing?"*
  * *"Is the victim breathing normally and responsive?"*
* **Phase 2 (Guidance):** Once key details are ascertained, the system switches to clear, imperative first aid instructions:
  * *"Apply continuous, firm two hand direct pressure over the wound using a clean cloth or folded shirt."*
  * *"Keep the victim lying completely flat on their back and cover them to preserve body warmth."*
  * *"Do not offer water or food while awaiting the ambulance team."*

### 5.3 Strict Non Diagnostic Safety Boundary
ResQ enforces uncompromising clinical safety boundaries to safeguard patient welfare:
1. **No Definitive Medical Diagnoses:** The system never issues medical diagnoses (such as *"The patient has an intracranial hemorrhage"*). It communicates solely in terms of observable physical presentations (such as *"Severe head injury with active bleeding"*).
2. **Zero Medication Prescriptions:** The system strictly prohibits recommending medications, pain relievers, or chemical treatments.
3. **Computer Vision Hazard Boundary:** Visual image recognition is strictly restricted to detecting environmental hazards (vehicle fires, fuel leaks, structural instability, flood depths). ResQ **never attempts to diagnose medical wounds from photographs.**

---

## 6. Mathematical Decision Models & Predictive Intelligence

ResQ integrates four mathematical modeling frameworks satisfying the designated IEEE crisis intelligence requirements:

### 6.1 ResQ Severity Index (RSI)
Every incident receives an objective numerical score between 1.0 (Minor) and 5.0 (Mass Casualty Critical) combining vital markers:

$$\text{RSI} = \min\left(5.0, \, \max\left(1.0, \, 1.0 + 1.2 \cdot C_v + 0.8 \cdot H_s + 0.5 \cdot \min(N_c - 1, 4) + 0.3 \cdot V_u\right)\right)$$

Where:
* $C_v \in \{0, 1\}$: Critical physiological flag (airway compromise, severe hemorrhage, unconsciousness).
* $H_s \in [0, 1]$: Environmental hazard magnitude (fuel leak, active blaze, high water).
* $N_c \ge 1$: Confirmed casualty count.
* $V_u \in \{0, 1\}$: Vulnerable demographic marker (infant, child, elderly patient).

### 6.2 Golden Hour Survival Probability Optimization
Trauma survival probability decays non linearly over transit elapsed time $t$:

$$S(t) = S_0 \cdot \exp(-\lambda_k \cdot t)$$

Where:
* $S_0$: Baseline survival probability at moment of injury.
* $\lambda_k$: Trauma decay coefficient ($0.035 \text{ min}^{-1}$ for blunt trauma; $0.075 \text{ min}^{-1}$ for massive hemorrhage).
* $t$: Transit travel duration to an appropriately equipped trauma facility.

The system selects destination trauma hospitals by maximizing expected survival rather than simply choosing the nearest basic clinic.

### 6.3 Spatial Corridor Crash Risk Index
Highway crash density along high speed transit corridors is evaluated using spatial kernel density estimations and Getis Ord $G_i^*$ statistics:

$$G_i^*(d) = \frac{\sum_{j=1}^n w_{ij} x_j - \bar{X} \sum_{j=1}^n w_{ij}}{S \sqrt{\frac{n \sum_{j=1}^n w_{ij}^2 - (\sum_{j=1}^n w_{ij})^2}{n - 1}}}$$

This identifies persistent spatial crash hotspots along the Enugu Onitsha Expressway and Ugwu Onyeama descent, allowing dispatchers to stage ambulance patrols proactively.

### 6.4 Hydro Meteorological Flood Inundation & Culvert Impassability
Culvert inundation probability along low lying drainage basins is calculated as:

$$P_{\text{flood}} = \frac{1}{1 + \exp\left(-\left(\beta_0 + \beta_1 \cdot R_{24} + \beta_2 \cdot S_{\text{slope}} - \beta_3 \cdot C_{\text{capacity}}\right)\right)}$$

Where $R_{24}$ is 24 hour rainfall accumulation, $S_{\text{slope}}$ is topographic elevation slope, and $C_{\text{capacity}}$ is culvert drainage volume. Roads flagged as flooded are automatically routed around for emergency vehicle transit.

---

## 7. Geographical Grounding: Enugu State Emergency Network

ResQ is calibrated specifically to the operational geography and health infrastructure of Enugu State, Nigeria:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ENUGU STATE TERTIARY TRAUMA NETWORK                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. ESUTH Parklane Hospital, GRA Enugu (6.4474° N, 7.5098° E)                          │
│    Level 1 State Trauma Facility · 24/7 Emergency Surgery · ICU · Blood Bank          │
│                                                                                        │
│ 2. University of Nigeria Teaching Hospital (UNTH), Ituku Ozalla (6.2847° N, 7.5081° E) │
│    Apex Federal Trauma Center · Cardiothoracic Center · Dedicated Neurotrauma Bay      │
│                                                                                        │
│ 3. National Orthopaedic Hospital Enugu (NOHE), Abakaliki Road (6.4522° N, 7.5255° E)   │
│    Apex Orthopedic & Specialized Burn Care Center · Severe Extrication Trauma Unit     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### High Risk Monitored Corridors & Flash Flood Basins:
* **The Ugwu Onyeama Descent (Enugu Onitsha Expressway):** Curved downhill gradient notorious for heavy freight truck brake failures, multi vehicle pileups, and tanker fuel fires.
* **9th Mile Corner Interchange:** Strategic freight transit hub linking northern and eastern highway corridors with heavy commercial congestion.
* **Ekulu and Asata River Basins:** Low lying culverts prone to rapid monsoon flash flooding along Ogui Road and Nike Lake Road corridors.

---

## 8. Live Hosted Platform Access & Evaluation Guide

**Evaluators, judges, and users can test ResQ immediately from any browser without installing software, cloning repositories, or running local servers.**

### Official Live Hosted Portals:
* **Master Navigation Hub:** `https://somachukwu.github.io/ResQ/`
* **Civilian Safety Portal:** `https://somachukwu.github.io/ResQ/civilian/`
* **Emergency Dispatch Command Portal:** `https://somachukwu.github.io/ResQ/dispatcher/`
* **Field Responder Heads Up HUD:** `https://somachukwu.github.io/ResQ/responder/`

---

### Step by Step Multi Screen Evaluation Walkthrough:

To observe the real time synchronization across all three roles, open three browser tabs or side by side windows:

#### Window 1: Civilian Portal (`https://somachukwu.github.io/ResQ/civilian/`)
1. Tap the large green **SOS Button**.
2. Type in plain English or Nigerian Pidgin:
   > *"Bad crash near Holy Ghost roundabout. Two victims, fuel is leaking from the vehicle and the driver has heavy head bleeding."*
3. Observe the AI assistant immediately acknowledging the situation, activating GPS location transmission, and asking targeted Phase 1 demographic and wound questions.
4. Reply with the victim details (*"Male driver, heavy blood coming from forehead"*).
5. Observe the assistant immediately transitioning to Phase 2 actionable WHO first aid guidance (firm two hand direct cloth pressure, keeping the patient flat).

#### Window 2: Dispatcher Command Center (`https://somachukwu.github.io/ResQ/dispatcher/`)
1. Observe the incident immediately appearing at the top of the priority incident queue flagged as **Critical Red (RSI $\ge$ 4.0)**.
2. Note the automated warning banner highlighting the **Fuel Leak Hazard**.
3. Click the incident card to inspect the live tactical console.
4. Click **Deploy Unit** and select **AMB 01** to allocate the nearest ambulance crew.
5. In the **Tactical Comms Console**, type an instruction to the bystander:
   > *"Keep clear of the leaking fuel. Emergency crew is rolling."*
6. Switch to the **Responder Channel** to coordinate directly with the ambulance crew.

#### Window 3: Field Responder Portal (`https://somachukwu.github.io/ResQ/responder/`)
1. Observe the screen populating instantly with the **10 Second Mission Brief**.
2. Review the incident summary, casualty count, and the critical **Fuel Leak Hazard Alert**.
3. Note the pre routed trauma hospital recommendation pointing to **ESUTH Parklane Hospital** with clinical justification.
4. Tap **Acknowledge Brief**.
5. Switch back to Window 1 (Civilian Portal) and observe that the live arrival ETA has synchronized to active countdown status (*"Unit AMB 01 En Route & Rolling"*).

#### Live WebRTC Voice Call Demonstration:
1. On Window 1 (Civilian Portal), tap **Call Command**.
2. Notice the outgoing call tone and instant incoming call modal pop up on Window 2 (Dispatcher Command Center).
3. On Window 2, click **Answer Call**.
4. Both ends immediately hear the dual tone connection chime followed by active voice channel presence.
5. Talk or listen across the audio channel, confirming bidirectional WebRTC audio transmission.
6. Click **End Call** on either window to cleanly disconnect the audio session.

---

## 9. Governance, Privacy & NDPA 2023 Compliance

ResQ is engineered in strict compliance with the **Nigeria Data Protection Act (NDPA 2023)**:
* **Zero Account Obligation:** Civilians report emergencies anonymously without mandatory accounts, passwords, or personal identity harvesting.
* **Ephemeral Incident Scope:** GPS coordinates and scene details are strictly anchored to an ephemeral Incident UUID and are never tied to individual identity profiles.
* **Data Minimization & Automated Purge:** Operational voice and location telemetry are archived for 30 days solely for statutory response auditing, after which operational logs are permanently purged.
* **Encrypted Data Transport:** All browser interactions operate under secure HTTPS and encrypted WSS WebSocket transport.

---

## 10. Conclusion & Operational Impact

ResQ demonstrates that pre hospital emergency mortality in developing regions can be dramatically lowered without waiting for multi billion dollar municipal infrastructure overhauls. 

By turning everyday smartphones into intelligent clinical sensors, bridging citizens directly to emergency controllers through encrypted browser audio, and enforcing algorithmic hospital selection during the Golden Hour, **ResQ delivers an emergency response intelligence platform built to save human lives today.**

*Built with precision for the IEEE Response Quest Challenge 2026.*
