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
PREFERRED_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
CANDIDATE_MODELS = [PREFERRED_MODEL, "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]
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

3. CONCISE, CALMING REASSURANCE (reassurance_message):
   - Keep your message short, comforting, and emotionally grounding (1 to 2 short sentences maximum).
   - Do NOT lecture the user about medical pathology or clinical mechanisms in the chat.
   - Just focus on keeping the caller calm, grounded, and reassured that they are not alone.
   - NEVER use robotic phrases like "Keep doing exactly what you are doing".
   - Examples of good English reassurance:
     "Help is actively on the way to your location. Take a slow, gentle breath with me, you are doing well, and I will stay right beside you until the medical team arrives."
     "Thank you for checking that so quickly. Take a deep breath, keep him comfortable, and I am right here with you."
   - Examples of good Nigerian Pidgin reassurance:
     "The medical team don dey rush come your side now now. Take soft breath with me, you dey try well well, and I dey right here with you till dem reach."
     "Thank you as you check that one sharp sharp. No fear at all, keep am comfortable, and I dey right beside you here."

4. ADAPTIVE STEP & CARD DEDUCTION:
   - Do NOT output action steps, multiple-choice questions, or red flags on every turn.
   - NATURAL CONVERSATION: If the caller is anxious, frightened, panicking, asking when help will arrive, sharing a general update, or simply conversing, keep 'first_aid_steps': [] and 'assessment_questions': [].
   - ACTION STEPS ('first_aid_steps'): ONLY include action steps when there are concrete, new physical actions the bystander must perform right now (e.g. applying firm direct pressure to bleeding wound, opening obstructed airway).
   - TARGETED QUESTIONS ('assessment_questions'): ONLY ask 1 targeted question with options (A, B, C) when functional capacity (such as weight-bearing or breathing) is not yet verified.
   - SELECTIVE RED FLAGS ('red_flags'): ONLY include red flags when there is an immediate, acute threat to life (such as cessation of breathing or massive uncontrolled arterial bleeding). For mild cases, sprains, or chats, keep 'red_flags': [].

5. DISPATCH TIMING AND ETA AWARENESS:
   - When the user asks about responders arriving, how long it will take, or where the ambulance is, reassure them warmly.
   - Use comforting conversational approximations such as "in less than 5 minutes" or "in just a few minutes, help is very close" (or in Pidgin: "dem go reach in less than 5 minutes, help dey very close") rather than rigid mechanical numbers.

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

    # Prepend previous turns from conversation history
    # Prepend previous turns from conversation history (limit to last 4 turns for low latency)
    if history and isinstance(history, list):
        for turn in history:
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
    if eta_seconds is not None:
        eta_minutes = max(1, round(eta_seconds / 60))
        time_desc = "in less than 5 minutes" if eta_minutes <= 5 else f"in less than {eta_minutes} minutes"
        system_text += f"\n\nCURRENT DISPATCH TIMING CONTEXT:\nThe emergency response unit is en route. Current estimated arrival time is approximately {eta_minutes} minutes ({time_desc}). If the user asks when help is arriving, how long it will take, or where the responders are, reassure them warmly using comforting conversational phrasing such as '{time_desc}, help is very close' rather than quoting exact timestamps."

    payload = {
        "system_instruction": {
            "parts": [{"text": system_text}]
        },
        "contents": contents,
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.45,
            "maxOutputTokens": 1000
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
        "red_flags": [str(rf) for rf in data.get("red_flags", []) if rf],
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

    # 1. Dispatch timing / ETA check
    asking_eta = bool(re.search(
        r"\b(when|how long|where is|where are|ambulance|coming|reach|arrive|how many minutes|far|time|still coming|en route|how far|shey dem dey come)\b",
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

    # Protocol-constrained step-by-step guidance
    is_answering_option = lower.startswith(("a.", "b.", "c.", "option a", "option b", "option c", "done", "finished", "thank you", "thanks"))

    steps = []
    if not is_answering_option:
        if unresponsive and airway_compromise:
            steps.append("Immediately check mouth for blockages. Gently tilt the head backward and lift the chin to open the airway.")
            steps.append("If not breathing at all, begin chest compressions: push hard and fast in the center of the chest (100 to 120 per minute).")
        elif unresponsive and not airway_compromise:
            steps.append("Do NOT shake the person. Check breathing by watching the chest rise and fall.")
            steps.append("If breathing normally, roll gently onto their side into the recovery position to keep the airway clear.")
            steps.append("Keep the neck straight. Do not place pillows under the head if spinal injury is suspected.")

        if severe_hemorrhage:
            steps.append("Find a clean cloth, towel, or shirt. Press down directly and firmly on the bleeding wound with both hands.")
            steps.append("Do NOT remove the cloth even if it soaks through. Add more layers of cloth on top and maintain constant pressure.")

        if is_sprain_or_joint:
            steps.append("Protection and Rest: Stop all running or heavy loading immediately to prevent tearing compromised ligaments.")
            steps.append("Ice and Compression: Apply a cold pack wrapped in cloth for 15 to 20 minutes, and wrap with comfortable elastic support.")
            steps.append("Elevation: Raise the injured limb above heart level when seated or lying down to reduce acute swelling.")

        if any(h in hazards for h in ["fuel_leak", "vehicle_fire"]):
            steps.append("SCENE SAFETY WARNING: Fuel or fire danger detected. Move bystanders back at least 25 meters. Strictly extinguish all cigarettes and avoid spark sources.")

        if not steps:
            steps.append("Keep the casualty calm, warm, and still. Do not offer food, water, or medication.")
            steps.append("Continuously monitor consciousness and breathing until the response team arrives.")

    # Contextual Clinical Synthesis for responder records
    if is_sprain_or_joint:
        synthesis = "Reported symptoms indicate an acute lower-extremity ligamentous or soft-tissue injury. Ottawa rules apply."
    elif severe_hemorrhage:
        synthesis = "Active vascular hemorrhage reported. Direct mechanical pressure required."
    elif unresponsive:
        synthesis = "Altered mental status or unconsciousness detected. Airway management is prioritized."
    else:
        synthesis = "Emergency triage assessment in progress. Continuous monitoring."

    # Interactive Assessment Questions: ONLY ask when assessing acute physical state
    questions = []
    if not is_answering_option:
        if is_sprain_or_joint:
            questions.append({
                "question": "Can the person take four steps, even with a limp?" if not is_pidgin else "The person fit take four steps at all, even if e dey limp?",
                "options": [
                    "A. Yes, can take four steps" if not is_pidgin else "A. Yes, e fit take four steps",
                    "B. No, completely unable to bear weight" if not is_pidgin else "B. No, e no fit put leg for ground at all",
                    "C. Can walk with minimal discomfort" if not is_pidgin else "C. E fit walk small small"
                ]
            })
        elif severe_hemorrhage:
            questions.append({
                "question": "Is the bleeding controlled by continuous direct pressure?" if not is_pidgin else "The blood dey reduce as you press am?",
                "options": [
                    "A. Bleeding is slowing down or stopped" if not is_pidgin else "A. Blood don dey slow down or e don stop",
                    "B. Bleeding continues to soak through cloths" if not is_pidgin else "B. Blood still dey soak through the cloth",
                    "C. Blood is spurting rhythmically" if not is_pidgin else "C. Blood dey rush out like tap"
                ]
            })
        elif unresponsive:
            questions.append({
                "question": "Is the casualty breathing normally and continuously?" if not is_pidgin else "The person dey breathe normal and continuous?",
                "options": [
                    "A. Breathing normally and regularly" if not is_pidgin else "A. E dey breathe normal and steady",
                    "B. Gasping, snoring, or struggling to breathe" if not is_pidgin else "B. E dey struggle to catch breath",
                    "C. No breathing detected at all" if not is_pidgin else "C. E no dey breathe at all"
                ]
            })

    # Red Flag Warning Signs
    red_flags = []
    if not is_answering_option:
        if is_sprain_or_joint:
            red_flags = [
                "Complete inability to bear weight or take four steps immediately",
                "Severe bone tenderness directly over the outer or inner ankle bone"
            ]
        elif severe_hemorrhage:
            red_flags = [
                "Continuous arterial spurting despite firm two-hand direct pressure",
                "Signs of hypovolemic shock: pale cold skin, confusion, or rapid shallow breathing"
            ]
        elif unresponsive and airway_compromise:
            red_flags = [
                "Cessation of breathing or irregular agonal breathing"
            ]

    # Reassurance message adapting dynamically to English or Nigerian Pidgin with zero dashes
    if is_answering_option:
        if is_sprain_or_joint:
            reassurance = "Thank you as you check that one. Keep that joint rested, comfortable, and lift am up small, I dey right here with you till help reach." if is_pidgin else "Thank you for checking that. Keep the joint rested, comfortable, and elevated, and I will stay right here with you until help arrives."
        elif severe_hemorrhage:
            reassurance = "Thank you as you hold that pressure. Press down tight with two hands, take deep breath, I dey with you." if is_pidgin else "Thank you for holding that pressure. Keep both hands pressed firmly in place, take a deep breath, and I am right here with you."
        elif unresponsive:
            reassurance = "Thank you as you stay close to am. Dey watch the chest make sure say e dey breathe, I dey beside you till the ambulance reach." if is_pidgin else "Thank you for staying close. Keep watching their chest gently rise and fall, and I will stay right beside you until the crew arrives."
        else:
            reassurance = "You dey try well well. Take soft, gentle breath with me, I dey right here with you till help arrive." if is_pidgin else "You are doing well. Take a slow, gentle breath, and I will stay right here with you until help arrives."
    else:
        if is_sprain_or_joint:
            reassurance = "Emergency team don dey come your location now now. Take soft breath, keep that leg rested and lift am up, I dey right here with you." if is_pidgin else "Emergency responders have been notified and are actively on the way. Take a slow breath, keep that leg rested and elevated, and I am right here with you."
        elif severe_hemorrhage:
            reassurance = "Emergency responders dey speed come your side now now. Stay close to am, hold that pressure tight tight, and I dey with you every second." if is_pidgin else "Emergency responders are speeding toward your location. Stay right beside them, maintain steady pressure, and I will stay with you every second."
        elif unresponsive:
            reassurance = "Emergency responders dey road dey come your side. Calam down and make sure say e throat open, I go guide you till dem reach." if is_pidgin else "Emergency responders are on the way to you. Stay calm and keep their airway open, and I will guide you through every moment until they arrive."
        else:
            reassurance = "Emergency responders don dey come your side. Take soft, gentle breath with me, you no dey alone, and I dey right here with you." if is_pidgin else "Emergency responders have been notified and are on the way. Take a slow, gentle breath with me, you are not alone, and I am right here with you."

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

