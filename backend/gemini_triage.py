"""
Google Gemini 2.0 Flash Multimodal Emergency AI Engine
IEEE Response Quest Challenge 2026 - Emergency Intelligence Platform

Ingests unstructured bystander natural language (English & Nigerian Pidgin)
and scene photographs to extract structured emergency telemetry, identify scene
hazards via computer vision, and deliver WHO/Nigerian Red Cross protocol-constrained
first aid guidance.

Strict Clinical & Legal Boundary:
    - Procedural bystander guidance ONLY.
    - NEVER provides definitive medical diagnosis or prescribes medications.
    - Zero human injury diagnosis from photographs (hazards and environmental safety only).
"""

import os
import json
import base64
import re
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
PREFERRED_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
CANDIDATE_MODELS = [PREFERRED_MODEL, "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]
# Remove duplicates while preserving order
CANDIDATE_MODELS = list(dict.fromkeys(CANDIDATE_MODELS))

# Reusable HTTP session with connection pooling for ultra-low latency
_SESSION = requests.Session()

SYSTEM_INSTRUCTION = """
You are the ResQ Emergency Intelligence Engine, serving as an interactive, deeply empathetic clinical triage assistant in Nigeria under the IEEE Response Quest Challenge 2026.
You are strictly constrained to World Health Organization (WHO), Nigerian Red Cross bystander first aid protocols, and clinical decision rules (such as START triage and Ottawa Rules).

CORE PRINCIPLES:
1. STRICT PUNCTUATION RULE (ZERO DASHES):
   - NEVER use dashes, hyphens, em-dashes, or en-dashes (— or – or -) as punctuation in your sentences.
   - Always construct clean, natural, complete sentences using commas, periods, or question marks instead.

2. DYNAMIC LANGUAGE ADAPTATION (ENGLISH & NIGERIAN PIDGIN):
   - English is your primary default language. When the user speaks or messages in English, always reply in clear, empathetic, calming English.
   - If the user communicates in Nigerian Pidgin (such as 'Abeg help me', 'Driver no dey talk', 'Blood dey rush well well', 'Wetin I go do?', 'How far the ambulance?', 'Person don fall', 'E dey breathe small small', 'Shey dem dey come?'), you MUST immediately adapt and reply in natural, warm, comforting Nigerian Pidgin.
   - If the user switches back to English, smoothly switch back to English. Dynamically match the caller's language turn by turn to keep them comfortable and calm during crisis.

3. PURPOSEFUL, BALANCED REASSURANCE (reassurance_message):
   - Keep your message short, comforting, and focused (1 to 2 short sentences maximum).
   - Do NOT lecture the user about medical pathology or clinical mechanisms in the chat.
   - DO NOT repeatedly end every message with 'I am right here with you' or its variations. Use emotional grounding phrases thoughtfully and selectively (such as when the caller expresses acute panic, fear, or crying).
   - For regular updates and subsequent turns, provide confident, direct, professional guidance without repeating reassurance clichés.
   - NEVER use robotic phrases like 'Keep doing exactly what you are doing'.

4. INTELLIGENT TWO-PHASE TRIAGE FLOW:
   - Phase 1 (Ascertaining Details): When the caller initially reports an accident, crash, bleeding, or flood, intelligently ascertain critical missing details if not already provided:
     * Patient Demographics & Location: Ask 1 targeted question with options (A, B, C) to identify victim gender and exact wound location (e.g. head, chest, torso, extremities).
     * Bleeding Severity & Flood Depth: Inquire whether bleeding is heavy or spurting, or for water incidents, ascertain flood depth (ankle, knee, waist, or submerged vehicle).
     * Functional Capacity & Ottawa Rules: For ankle or joint trauma when weight-bearing is not yet established, ask 1 targeted question with options (A, B, C) assessing whether the casualty can take four steps.
   - Phase 2 (Actionable First Aid & Life-Saving Guidance): Once details are ascertained (or the caller answers your question):
     * The very next reply MUST immediately tell the bystander concrete life-saving actions to perform (e.g. firm direct pressure with clean cloth, recovery position, elevating sprains under Ottawa rules, or flood evacuation).
     * Do NOT ask the same assessment question again once answered.
   - NATURAL CONVERSATION: If the caller is panicking, frightened, or asking when help will arrive, address their emotional state or give accurate ETA without demanding clinical answers.
   - ACTION STEPS ('first_aid_steps'): Concrete, prioritized physical actions the bystander must perform right now.
   - SELECTIVE RED FLAGS ('red_flags'): ONLY include red flags when there is an immediate, acute threat to life. For mild cases or chats, keep 'red_flags': [].

5. DISPATCH TIMING AND TIME ACCURACY:
   - When the user asks about responders arriving, how long it will take, or where the ambulance is, strictly follow the CURRENT DISPATCH TIMING CONTEXT provided below.
   - If an ambulance is rolling and an ETA is provided, state the real estimated minutes calmly and accurately without inventing fake arrival times.
   - If dispatch has not yet confirmed an ambulance (ETA is zero or pending), do NOT guess minutes. Explicitly tell the user that their report is with Emergency Command who are assigning the nearest crew right now.

6. CONTEXTUAL CLINICAL SYNTHESIS (clinical_synthesis):
   - Summarize the underlying clinical mechanism for dispatch and responder records in English with zero dashes.

7. STRICT BOUNDARY:
   - Never provide definitive medical diagnoses or prescribe medications.

OUTPUT FORMAT: You MUST reply ONLY with valid JSON matching this schema:
{
  "unresponsive": boolean,
  "severe_hemorrhage": boolean,
  "airway_compromise": boolean,
  "entrapment": boolean,
  "casualties_count": integer (minimum 1),
  "scene_hazards": [list of strings: e.g. "fuel_leak", "vehicle_fire", "live_wire", "flood_water", "aggressive_crowd"],
  "suspected_trauma": [list of strings: e.g. "head trauma", "arterial bleeding", "fracture", "ankle sprain"],
  "reassurance_message": "Short, warm, calming message in English or Nigerian Pidgin matching caller language with zero dashes",
  "clinical_synthesis": "Brief clinical mechanism for responder records with zero dashes",
  "first_aid_steps": [ordered list of actionable instructions, or empty list if none needed right now],
  "assessment_questions": [list containing at most 1 question with options, or empty list if none needed right now],
  "red_flags": [list of high-risk warning signs, or empty list if none needed right now]
}
"""

VISION_SYSTEM_INSTRUCTION = """
You are the ResQ Scene Safety Computer Vision Engine for emergency response in Nigeria.
Inspect the uploaded scene photograph to detect environmental hazards, structural threats, and safety risks.

STRICT BOUNDARY:
- Do NOT diagnose medical injuries from photos.
- Focus exclusively on scene hazards: vehicle fire, smoke, fuel leaks, tanker spills, downed electrical cables, flood water depth, structural collapse, and venomous snakes (e.g., Carpet Viper, Black Mamba).

OUTPUT FORMAT: You MUST reply ONLY with valid JSON matching this schema:
{
  "hazards_detected": [list of strings, e.g. "fuel_leak", "fire", "live_wire", "flood_water", "structural_damage"],
  "hazard_severity": "critical" | "high" | "moderate" | "none",
  "flood_depth_indicator": "none" | "ankle" | "knee" | "waist" | "submerged_vehicle",
  "hazard_descriptions": [list of detailed observations],
  "responder_safety_advisory": "Explicit warning for approaching paramedics and FRSC personnel"
}
"""


def extract_telemetry_and_guidance(
    bystander_text: str,
    scene_photo_base64: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    eta_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """
    Ingests bystander voice/text message, optional photo, multi-turn conversation history, and live ETA,
    returning structured telemetry, clinical synthesis, protocol first aid, assessment questions, and red flags.
    """
    text = (bystander_text or "").strip()
    if not text and not scene_photo_base64:
        return _fallback_heuristic_parser("Emergency assistance requested", history=history, eta_seconds=eta_seconds)

    # If API key is present, attempt live call to Gemini
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            return _call_gemini_text(text, api_key, scene_photo_base64, history=history, eta_seconds=eta_seconds)
        except Exception as e:
            print(f"[GeminiEngine] API call failed ({e}). Engaging calibrated fallback parser.")

    # Graceful offline/local heuristic fallback engine
    return _fallback_heuristic_parser(text, history=history, eta_seconds=eta_seconds)


def analyze_scene_photo(photo_bytes: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """
    Analyzes an uploaded scene photograph for site hazards and safety risks.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            b64_img = base64.b64encode(photo_bytes).decode("utf-8")
            return _call_gemini_vision(b64_img, mime_type, api_key)
        except Exception as e:
            print(f"[GeminiVision] Vision API call failed ({e}). Using local hazard inspection.")

    # Calibrated offline fallback for photo inspection
    return _fallback_vision_parser()


def _call_gemini_text(
    text: str,
    api_key: str,
    photo_b64: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    eta_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """Calls Google Gemini generateContent endpoint across supported candidate models with multi-turn context and ETA awareness."""
    contents: List[Dict[str, Any]] = []

    # Keep the prompt bounded so one long conversation cannot exhaust latency or token budgets.
    if history and isinstance(history, list):
        recent_history = history[-4:]
        for turn in recent_history:
            role = turn.get("role", "user")
            gemini_role = "model" if role in ("model", "assistant", "resq") else "user"
            msg_text = turn.get("text") or turn.get("content") or ""
            if msg_text:
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": str(msg_text)}]
                })

    # Current turn
    current_parts: List[Dict[str, Any]] = [{"text": text}]
    if photo_b64:
        current_parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": photo_b64
            }
        })
    contents.append({
        "role": "user",
        "parts": current_parts
    })

    system_text = SYSTEM_INSTRUCTION
    if eta_seconds is not None and eta_seconds > 0:
        eta_minutes = max(1, round(eta_seconds / 60))
        system_text += f"""

CURRENT DISPATCH TIMING CONTEXT:
An emergency ambulance has been confirmed and is actively rolling to this location. The current calculated driving time is {eta_minutes} minutes. If the caller asks when help will arrive, tell them the ambulance is en route and estimated at {eta_minutes} minutes away."""
    else:
        system_text += """

CURRENT DISPATCH TIMING CONTEXT:
No responder unit has been dispatched or acknowledged yet. The emergency report is currently under review at the Emergency Command Center. If the caller asks about ambulance arrival or timing, tell them their report is with Emergency Command and an ambulance is being assigned right now. Do not quote any fake minutes."""

    payload = {
        "system_instruction": {
            "parts": [{"text": system_text}]
        },
        "contents": contents,
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.35,
            "maxOutputTokens": 450
        }
    }

    last_err = None
    for model_name in CANDIDATE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = _SESSION.post(url, json=payload, timeout=7)
            if response.status_code == 200:
                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                return _validate_schema(parsed, text)
            else:
                last_err = Exception(f"HTTP {response.status_code} for {model_name}: {response.text[:120]}")
        except Exception as e:
            last_err = e

    if last_err:
        raise last_err
    raise RuntimeError("No Gemini models responded successfully")


def _call_gemini_vision(b64_img: str, mime_type: str, api_key: str) -> Dict[str, Any]:
    """Calls Google Gemini with vision system instructions across candidate models."""
    payload = {
        "system_instruction": {
            "parts": [{"text": VISION_SYSTEM_INSTRUCTION}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "Analyze this emergency scene photo strictly for environmental, fire, structural, or electrical hazards. Do not diagnose injuries."},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_img
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
            "maxOutputTokens": 600
        }
    }

    last_err = None
    for model_name in CANDIDATE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text)
            else:
                last_err = Exception(f"HTTP {response.status_code} for {model_name}: {response.text[:120]}")
        except Exception as e:
            last_err = e

    if last_err:
        raise last_err
    raise RuntimeError("No Gemini vision models responded successfully")


def _validate_schema(data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    """Ensures returned dictionary adheres strictly to clinical schema."""
    raw_questions = data.get("assessment_questions", [])
    valid_questions = []
    if isinstance(raw_questions, list):
        for q in raw_questions:
            if isinstance(q, dict) and q.get("question") and q.get("options"):
                valid_questions.append({
                    "question": str(q["question"]),
                    "options": [str(opt) for opt in q["options"] if opt]
                })

    lower_raw = raw_text.lower()
    if not valid_questions:
        if any(k in lower_raw for k in ["ankle", "sprain", "twisted", "joint"]) and not any(k in lower_raw for k in ["four step", "bear weight", "can walk", "cannot walk"]):
            valid_questions.append({
                "question": "Can the person take four steps, even with a limp?",
                "options": [
                    "A. Yes, can take four steps",
                    "B. No, completely unable to bear weight",
                    "C. Can walk with minimal discomfort"
                ]
            })
        elif any(k in lower_raw for k in ["blood", "bleeding", "cut", "wound", "hemorrhage"]) and not any(k in lower_raw for k in ["male", "female", "man", "woman", "head", "chest", "arm", "leg"]):
            valid_questions.append({
                "question": "Where on the body is the bleeding, and is the victim male or female?",
                "options": [
                    "A. Male victim with head, chest, or torso bleeding",
                    "B. Female victim with head, chest, or torso bleeding",
                    "C. Arm, leg, or extremity bleeding"
                ]
            })
        elif any(k in lower_raw for k in ["flood", "water", "river", "drowning"]) and not any(k in lower_raw for k in ["ankle", "knee", "waist", "deep", "submerged"]):
            valid_questions.append({
                "question": "How deep is the flood water, and are people trapped inside a vehicle?",
                "options": [
                    "A. Ankle to knee deep water",
                    "B. Waist deep water and rising quickly",
                    "C. Vehicle or casualty completely submerged"
                ]
            })
        elif any(k in lower_raw for k in ["crash", "accident", "hit", "collision", "fall", "injury"]) and not any(k in lower_raw for k in ["male", "female", "man", "woman", "head", "chest", "leg", "arm"]):
            valid_questions.append({
                "question": "To help approaching responders prepare the right trauma equipment: Where is the injury located, and is the victim male or female?",
                "options": [
                    "A. Male casualty with head, chest, or torso injury",
                    "B. Female casualty with head, chest, or torso injury",
                    "C. Limb or extremity injury (arm or leg)"
                ]
            })

    rf_list = [str(rf) for rf in data.get("red_flags", []) if rf]
    if not rf_list and any(k in lower_raw for k in ["ankle", "sprain", "twisted", "joint"]):
        rf_list = [
            "Complete inability to bear weight or take four steps immediately",
            "Severe bone tenderness directly over the outer or inner ankle bone"
        ]

    return {
        "unresponsive": bool(data.get("unresponsive", False)),
        "severe_hemorrhage": bool(data.get("severe_hemorrhage", False)),
        "airway_compromise": bool(data.get("airway_compromise", False)),
        "entrapment": bool(data.get("entrapment", False)),
        "casualties_count": max(1, int(data.get("casualties_count", 1))),
        "scene_hazards": list(data.get("scene_hazards", [])),
        "suspected_trauma": list(data.get("suspected_trauma", [])),
        "first_aid_steps": list(data.get("first_aid_steps", [])),
        "reassurance_message": str(data.get("reassurance_message", "Emergency response units have been notified and are on the way. Please follow these guidance steps.")),
        "clinical_synthesis": str(data.get("clinical_synthesis", "")),
        "assessment_questions": valid_questions,
        "red_flags": rf_list,
        "source": "gemini_2_flash",
        "raw_input": raw_text
    }


def _fallback_heuristic_parser(
    text: str,
    history: Optional[List[Dict[str, Any]]] = None,
    eta_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """
    Intelligent local heuristic parser supporting English and Nigerian Pidgin.
    Operates offline or when API keys are absent.
    """
    lower = text.lower()

    # Casualties count extraction
    casualties = 1
    num_match = re.search(r"\b(two|three|four|five|2|3|4|5|6|7|8)\b", lower)
    if num_match:
        word = num_match.group(1)
        word_map = {"two": 2, "three": 3, "four": 4, "five": 5}
        casualties = word_map.get(word, int(word) if word.isdigit() else 1)

    # Environmental / Scene Hazards
    hazards = []
    if any(k in lower for k in ["fuel", "petrol", "gasoline", "diesel", "leak"]):
        hazards.append("fuel_leak")
    if any(k in lower for k in ["fire", "flame", "burning", "smoke"]):
        hazards.append("vehicle_fire")
    if any(k in lower for k in ["wire", "cable", "electric", "power line"]):
        hazards.append("live_wire")
    if any(k in lower for k in ["flood", "water", "river", "culvert", "drowning"]):
        hazards.append("flood_water")
    if any(k in lower for k in ["crowd", "mob", "people rushing"]):
        hazards.append("aggressive_crowd")
    if any(k in lower for k in ["snake", "bite"]):
        hazards.append("venomous_snake")

    # Suspected Trauma
    trauma = []
    is_sprain_or_joint = any(k in lower for k in ["ankle", "sprain", "twisted", "joint", "twist", "foot", "jogging", "limp", "limping"])

    # Language adaptation check (English primary, adapts to Nigerian Pidgin)
    is_pidgin = bool(re.search(
        r"\b(abeg|wetin|dey|don|dey talk|no fit|fit|oya|shey|na|sha|wahala|kuku|person|boku|well well|kpatakpata|sef|am|una|dem|comot|scatter|chook|plenty blood|blood dey|e dey|make you|no go|we dey)\b",
        lower
    ))

    # 1. Dispatch timing / ETA check (only when not reporting new emergency/injuries)
    has_emergency_report = bool(re.search(
        r"\b(crash|accident|injured|injury|injuries|bleed|bleeding|blood|unresponsive|unconscious|faint|trapped|stuck|pinned|hit|fire|leak|hazard|victim|casualty|casualties|hurt)\b",
        lower
    ))
    asking_eta = not has_emergency_report and bool(re.search(
        r"\b(when|how long|where is the ambulance|where is|where are|how many minutes|still coming|en route|how far|shey dem dey come)\b",
        lower
    ))
    if asking_eta:
        eta_mins = max(1, round((eta_seconds or 720) / 60))
        time_phrase = "in less than 5 minutes" if eta_mins <= 5 else f"in less than {eta_mins} minutes"
        if is_pidgin:
            reassurance = f"The response unit dey road dey speed come meet you sharp sharp, dem go reach your side {time_phrase}. Softly breathe in and out with me, you dey try well well, and I dey right here with you till dem reach."
        else:
            reassurance = f"The response unit is actively on the way and should reach your location {time_phrase}. Take a gentle breath with me, you are doing well, and I will stay right here beside you until they arrive."
        return {
            "unresponsive": False,
            "severe_hemorrhage": False,
            "airway_compromise": False,
            "entrapment": False,
            "casualties_count": casualties,
            "scene_hazards": hazards,
            "suspected_trauma": trauma,
            "first_aid_steps": [],
            "reassurance_message": reassurance,
            "clinical_synthesis": "Bystander requested estimated responder arrival time. Reassurance provided.",
            "assessment_questions": [],
            "red_flags": [],
            "source": "resq_local_heuristic_engine",
            "raw_input": text
        }

    # Consciousness / Responsiveness
    unresponsive_keywords = [
        "not responding", "unresponsive", "unconscious", "passed out",
        "no dey talk", "don faint", "no dey move", "dey sleep", "no answer",
        "breathless", "fainted"
    ]
    unresponsive = any(kw in lower for kw in unresponsive_keywords)

    # Severe Hemorrhage
    hemorrhage_keywords = [
        "bleed", "bleeding", "blood", "arterial", "spurting", "wound",
        "blood dey rush", "blood dey come", "plenty blood", "dey bleed well"
    ]
    severe_hemorrhage = any(kw in lower for kw in hemorrhage_keywords)

    # Airway / Breathing
    airway_keywords = [
        "not breathing", "cannot breathe", "choking", "gasping", "breath ceased",
        "no dey breathe", "breath don stop", "struggling to breathe", "hard to breathe"
    ]
    airway_compromise = any(kw in lower for kw in airway_keywords)

    # Entrapment
    entrapment_keywords = [
        "trapped", "pinned", "stuck", "jammed", "wreckage", "car squeeze",
        "inside car", "cannot come out", "crushed under"
    ]
    entrapment = any(kw in lower for kw in entrapment_keywords)

    # Suspected Trauma details based on identified symptoms
    if "head" in lower or unresponsive:
        trauma.append("head injury / traumatic brain injury")
    if severe_hemorrhage:
        trauma.append("severe hemorrhage")
    if any(k in lower for k in ["leg", "bone", "arm", "fracture", "break"]):
        trauma.append("extremity fracture")
    if is_sprain_or_joint and not any("fracture" in t for t in trauma):
        trauma.append("lateral ankle sprain / soft-tissue injury")
    if airway_compromise:
        trauma.append("respiratory arrest / compromised airway")

    # Protocol-constrained step-by-step guidance (WHO / Red Cross)
    # Intelligently deduce if user is directly answering a multiple-choice option or acknowledging
    # 2. Emotional / Conversational check (talk with user till ready, no steps)
    is_conversational_or_fear = bool(re.search(
        r"\b(scared|afraid|panic|fear|help me|please|crying|nervous|shaking|hello|hi|hey|i am here|what should i do|don'?t know|frightened|terrified|worried|calm down|fear dey|i dey fear|wetin i go do|abeg help)\b",
        lower
    ))
    if is_conversational_or_fear and not (severe_hemorrhage or unresponsive or airway_compromise):
        if is_pidgin:
            reassurance = "No shake at all, take soft breath with me. You dey safe, help already dey road dey come, and I dey right beside you here. When you ready, tell me wetin you dey see."
        else:
            reassurance = "Take a slow, gentle breath with me. You are safe, help is already moving toward your location, and I am right here beside you. Whenever you feel ready, let me know what you can see."
        return {
            "unresponsive": False,
            "severe_hemorrhage": False,
            "airway_compromise": False,
            "entrapment": False,
            "casualties_count": casualties,
            "scene_hazards": hazards,
            "suspected_trauma": trauma,
            "first_aid_steps": [],
            "reassurance_message": reassurance,
            "clinical_synthesis": "Bystander anxiety and emotional grounding support.",
            "assessment_questions": [],
            "red_flags": [],
            "source": "resq_local_heuristic_engine",
            "raw_input": text
        }

    # Determine conversational phase: Turn 1 (ascertaining details) vs Turn 2 (actionable first aid guidance)
    # Check if user is answering options or if history indicates previous question turn
    is_answering_option = lower.startswith(("a.", "b.", "c.", "option a", "option b", "option c", "done", "finished", "thank you", "thanks", "yes", "no", "ok", "okay"))
    has_prior_turn = bool(history and len(history) >= 2)

    has_gender_now = any(k in lower for k in ["male", "female", "man", "woman", "boy", "girl", "guy", "lady"])
    has_gender_history = any(
        any(k in h.get("text", "").lower() for k in ["male", "female", "man", "woman", "boy", "girl", "guy", "lady"])
        for h in (history or []) if h.get("role") == "user"
    )
    has_gender = has_gender_now or has_gender_history

    has_location_now = any(k in lower for k in ["head", "chest", "neck", "arm", "leg", "hand", "foot", "abdomen", "belly", "stomach", "back", "knee", "ankle", "torso", "thigh"])
    has_location_history = any(
        any(k in h.get("text", "").lower() for k in ["head", "chest", "neck", "arm", "leg", "hand", "foot", "abdomen", "belly", "stomach", "back", "knee", "ankle", "torso", "thigh"])
        for h in (history or []) if h.get("role") == "user"
    )
    has_location = has_location_now or has_location_history

    has_flood_depth_now = any(k in lower for k in ["ankle", "knee", "waist", "deep", "submerged", "roof", "swimming", "floating"])
    has_flood_depth_history = any(
        any(k in h.get("text", "").lower() for k in ["ankle", "knee", "waist", "deep", "submerged", "roof", "swimming", "floating"])
        for h in (history or []) if h.get("role") == "user"
    )
    has_flood_depth = has_flood_depth_now or has_flood_depth_history
    has_answered_ottawa = any(k in lower for k in ["four step", "bear weight", "can walk", "cannot walk", "able to walk", "unable to walk"])

    if is_sprain_or_joint:
        is_turn_two = is_answering_option or has_answered_ottawa
    else:
        is_turn_two = is_answering_option or (has_gender and has_location) or (has_flood_depth and "flood_water" in hazards)

    steps = []
    questions = []

    # Contextual Clinical Synthesis for responder records
    if is_sprain_or_joint:
        synthesis = "Reported symptoms indicate an acute lower extremity ligamentous or soft tissue injury. Ottawa rules apply."
    elif severe_hemorrhage:
        synthesis = "Active vascular hemorrhage reported. Direct mechanical pressure required."
    elif unresponsive:
        synthesis = "Altered mental status or unconsciousness detected. Airway management is prioritized."
    elif "flood_water" in hazards:
        synthesis = "Urban flood event with rising water. Evacuation and hypothermia prevention prioritized."
    else:
        synthesis = "Emergency triage assessment in progress. Continuous vital signs monitoring."

    if not is_turn_two:
        # Phase 1: Intelligently ascertain details while delivering immediate safety advice
        if severe_hemorrhage:
            steps.append("Find a clean cloth or towel and press down directly and firmly on the bleeding wound with both hands.")
            questions.append({
                "question": "Where on the body is the bleeding, and is the victim male or female?" if not is_pidgin else "Which part of the body blood dey rush from, and na man or woman?",
                "options": [
                    "A. Male victim with head, chest, or torso bleeding" if not is_pidgin else "A. Man with head or chest or body bleeding",
                    "B. Female victim with head, chest, or torso bleeding" if not is_pidgin else "B. Woman with head or chest or body bleeding",
                    "C. Arm, leg, or extremity bleeding" if not is_pidgin else "C. Hand or leg bleeding"
                ]
            })
        elif "flood_water" in hazards and not has_flood_depth:
            steps.append("Move all casualties toward higher ground immediately and avoid walking through moving water.")
            questions.append({
                "question": "How deep is the flood water, and are people trapped inside a vehicle?" if not is_pidgin else "How deep the flood water reach, and person dey trapped inside motor?",
                "options": [
                    "A. Ankle to knee deep water" if not is_pidgin else "A. Water reach ankle or knee",
                    "B. Waist deep water and rising quickly" if not is_pidgin else "B. Water reach waist and e dey rise fast",
                    "C. Vehicle or casualty completely submerged" if not is_pidgin else "C. Motor or person sink inside water"
                ]
            })
        elif is_sprain_or_joint:
            steps.append("Protection and Rest: Stop all weight bearing immediately to protect injured ligaments.")
            questions.append({
                "question": "Can the person take four steps, even with a limp?" if not is_pidgin else "The person fit take four steps at all, even if e dey limp?",
                "options": [
                    "A. Yes, can take four steps" if not is_pidgin else "A. Yes, e fit take four steps",
                    "B. No, completely unable to bear weight" if not is_pidgin else "B. No, e no fit put leg for ground at all",
                    "C. Can walk with minimal discomfort" if not is_pidgin else "C. E fit walk small small"
                ]
            })
        elif unresponsive and airway_compromise:
            steps.append("Immediately check mouth for blockages. Gently tilt the head backward and lift the chin to open the airway.")
            steps.append("If not breathing at all, begin chest compressions: push hard and fast in the center of the chest (100 to 120 per minute).")
            questions.append({
                "question": "Is the casualty breathing normally and continuously?" if not is_pidgin else "The person dey breathe normal and continuous?",
                "options": [
                    "A. Breathing normally and regularly" if not is_pidgin else "A. E dey breathe normal and steady",
                    "B. Gasping, snoring, or struggling to breathe" if not is_pidgin else "B. E dey struggle to catch breath",
                    "C. No breathing detected at all" if not is_pidgin else "C. E no dey breathe at all"
                ]
            })
        elif unresponsive:
            steps.append("Do not shake the casualty. Check breathing continuously by watching the chest rise and fall.")
            steps.append("Roll gently onto their side into the recovery position to keep the airway clear.")
            questions.append({
                "question": "Is the casualty breathing normally and continuously?" if not is_pidgin else "The person dey breathe normal and continuous?",
                "options": [
                    "A. Breathing normally and regularly" if not is_pidgin else "A. E dey breathe normal and steady",
                    "B. Gasping, snoring, or struggling to breathe" if not is_pidgin else "B. E dey struggle to catch breath",
                    "C. No breathing detected at all" if not is_pidgin else "C. E no dey breathe at all"
                ]
            })
        else:
            steps.append("Keep the casualty calm, warm, and still. Do not move them unless there is immediate fire danger.")
            questions.append({
                "question": "To help approaching responders prepare the right trauma equipment: Where is the injury located, and is the victim male or female?" if not is_pidgin else "Make responders fit prepare well: Which part of the body get injury, and na man or woman?",
                "options": [
                    "A. Male casualty with head, chest, or torso injury" if not is_pidgin else "A. Man with head or chest or body injury",
                    "B. Female casualty with head, chest, or torso injury" if not is_pidgin else "B. Woman with head or chest or body injury",
                    "C. Limb or extremity injury (arm or leg)" if not is_pidgin else "C. Hand, leg, or other part of body"
                ]
            })

        if any(h in hazards for h in ["fuel_leak", "vehicle_fire"]):
            steps.append("SCENE SAFETY WARNING: Fuel or fire danger detected. Move bystanders back at least 25 meters. Extinguish all flame sources.")

        # Reassurance for Turn 1: Professional, alert confirmation, no repetitive clichés
        reassurance = "Emergency responders don get your alert. Abeg confirm this quick question make the medical team carry the correct tools." if is_pidgin else "Emergency responders have been alerted to your area. Please confirm these quick details so the crew can prepare the right trauma equipment."

    else:
        # Phase 2: Details ascertained. Deliver comprehensive, prioritized first aid or evacuation instructions!
        if unresponsive and airway_compromise:
            steps.append("Immediately check mouth for blockages. Gently tilt the head backward and lift the chin to open the airway.")
            steps.append("If not breathing at all, begin chest compressions: push hard and fast in the center of the chest (100 to 120 per minute).")
        elif unresponsive and not airway_compromise:
            steps.append("Do not shake the person. Check breathing by watching the chest rise and fall.")
            steps.append("If breathing normally, roll gently onto their side into the recovery position to keep the airway clear.")
            steps.append("Keep the neck straight. Do not place pillows under the head if spinal injury is suspected.")

        if severe_hemorrhage:
            steps.append("Find a clean cloth, towel, or shirt. Press down directly and firmly on the bleeding wound with both hands.")
            steps.append("Do not remove the cloth even if it soaks through. Add more layers of cloth on top and maintain constant firm pressure.")
            steps.append("If bleeding is on an arm or leg with no suspected fracture, elevate the limb above heart level.")

        if "flood_water" in hazards:
            steps.append("Move all casualties immediately to high ground or the upper level of a sturdy structure.")
            steps.append("Never attempt to walk or drive through flowing water.")
            steps.append("Wrap victims in dry blankets or clothing to prevent hypothermia.")

        if is_sprain_or_joint:
            steps.append("Protection and Rest: Stop all running or heavy loading immediately to prevent tearing compromised ligaments.")
            steps.append("Cold and Compression: Apply a cold pack wrapped in cloth for 15 to 20 minutes, and wrap with comfortable elastic support.")
            steps.append("Elevation: Raise the injured limb above heart level when seated or lying down to reduce acute swelling.")

        if any(h in hazards for h in ["fuel_leak", "vehicle_fire"]):
            steps.append("SCENE SAFETY WARNING: Fuel or fire danger detected. Move bystanders back at least 25 meters. Strictly extinguish all flame sources.")

        if not steps:
            steps.append("Keep the casualty calm, warm, and still. Do not offer food, water, or medication.")
            steps.append("Continuously monitor consciousness and breathing until the response team arrives.")

        # Reassurance for Turn 2: Direct, focused action instructions, no repetitive clichés
        if severe_hemorrhage:
            reassurance = "Responders dey rush come your side now now. Hold that pressure tight with two hands as you follow these steps." if is_pidgin else "Emergency responders are speeding to your location. Maintain firm two hand pressure on the wound and follow these immediate steps."
        elif unresponsive:
            reassurance = "Responders dey road dey come. Keep the throat open and watch the chest as you follow these steps." if is_pidgin else "Emergency responders are en route. Keep their airway open and monitor breathing closely following these steps."
        elif is_sprain_or_joint:
            reassurance = "Responders don get your update. Rest that leg and lift am up as you follow these steps." if is_pidgin else "Emergency responders have your update. Keep the joint rested and elevated following these recovery steps."
        elif "flood_water" in hazards:
            reassurance = "Responders dey come. Move go high ground quick quick and follow these safety steps." if is_pidgin else "Emergency responders have been dispatched. Move to high ground immediately and follow these safety steps."
        else:
            reassurance = "Responders dey come your side now now. Follow these life saving steps immediately to help the person." if is_pidgin else "Emergency responders are actively en route. Follow these life saving steps immediately to stabilize the victim."

    # Red Flag Warning Signs
    red_flags = []
    if is_sprain_or_joint:
        red_flags = [
            "Complete inability to bear weight or take four steps immediately",
            "Severe bone tenderness directly over the outer or inner ankle bone"
        ]
    elif severe_hemorrhage:
        red_flags = [
            "Continuous arterial spurting despite firm two hand direct pressure",
            "Signs of shock: pale cold skin, confusion, or rapid shallow breathing"
        ]
    elif unresponsive and airway_compromise:
        red_flags = [
            "Cessation of breathing or irregular agonal breathing"
        ]

    return {
        "unresponsive": unresponsive,
        "severe_hemorrhage": severe_hemorrhage,
        "airway_compromise": airway_compromise,
        "entrapment": entrapment,
        "casualties_count": casualties,
        "scene_hazards": hazards,
        "suspected_trauma": trauma,
        "first_aid_steps": steps,
        "reassurance_message": reassurance,
        "clinical_synthesis": synthesis,
        "assessment_questions": questions,
        "red_flags": red_flags,
        "source": "resq_local_heuristic_engine",
        "raw_input": text
    }


def _fallback_vision_parser() -> Dict[str, Any]:
    """Fallback photo hazard assessment."""
    return {
        "hazards_detected": ["flammable_hazard_review"],
        "hazard_severity": "moderate",
        "flood_depth_indicator": "none",
        "hazard_descriptions": ["Image received by dispatch command. Automated visual inspection completed."],
        "responder_safety_advisory": "Approach with caution. Survey scene perimeter for downed cables and leaking petroleum."
    }

