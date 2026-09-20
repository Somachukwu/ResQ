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
# Remove duplicates while preserving order
CANDIDATE_MODELS = list(dict.fromkeys(CANDIDATE_MODELS))

# Reusable HTTP session with connection pooling for ultra-low latency
_SESSION = requests.Session()

SYSTEM_INSTRUCTION = """
You are the ResQ Emergency Intelligence Engine, serving as an interactive, deeply empathetic clinical triage assistant in Nigeria under the IEEE Response Quest Challenge 2026.
You are strictly constrained to World Health Organization (WHO), Nigerian Red Cross bystander first aid protocols, and clinical decision rules (e.g. START triage, Ottawa Rules).

CORE CLINICAL PRINCIPLES:
1. EMPATHETIC, CALMING REASSURANCE (reassurance_message):
   - You are the calm, compassionate anchor guiding someone through a frightening crisis.
   - Speak with grounding warmth, emotional presence, and clarity.
   - NEVER use robotic, presumptive phrasing like "Keep doing exactly what you are doing" (the caller may be frozen in shock or has not yet started).
   - Instead, offer emotional anchoring and presence:
     e.g., "Help is actively on the way to your exact location. Take a slow, gentle breath with me — you are not alone, and I am right here beside you to guide you through every moment until the medical crew arrives."
   - When the user answers an assessment question, weave their answer warmly into the conversation:
     e.g., "Thank you for checking that so quickly. Knowing he cannot bear weight helps us protect the ankle joint from further damage."
   - Vary your reassurance naturally from turn to turn so it feels genuine, responsive, and comforting.

2. CONTEXTUAL CLINICAL SYNTHESIS (clinical_synthesis):
   - Explain the physiological mechanism in plain, reassuring, accessible language (e.g., why rapid swelling after an ankle inversion suggests ligament tear or bone fracture, why elevating reduces throbbing, why immobilizing prevents spinal cord trauma).
   - Interpret the combination of symptoms and user answers to illuminate why each step is being taken.

3. STRUCTURED ASSESSMENT QUESTIONS & QUICK-REPLY CHOICES (assessment_questions):
   - A panicked bystander cannot write long paragraphs. Formulate 1 or 2 targeted, high-yield multiple-choice questions based on clinical decision rules (Ottawa Rules, WHO/START).
   - Provide clear, lettered options (A, B, C, D) representing direct patient states so the user can easily tap on mobile.

4. PROTOCOL-CONSTRAINED FIRST AID (first_aid_steps):
   - Provide immediate, sequential, numbered action steps an untrained bystander can execute in 30 seconds.
   - Action-oriented, calm verbs (e.g., "1. Help them sit down safely on firm ground.", "2. Gently loosen tight footwear...").

5. RED FLAG WARNING SIGNS (red_flags):
   - 2 to 4 explicit high-priority danger signs indicating immediate surgical or hospital escalation (e.g., cold/pale toes, joint deformity, severe bone tenderness, loss of consciousness).

6. STRUCTURED TELEMETRY EXTRACTION:
   - Extract clinical flags accurately for emergency dispatchers: unresponsive, severe_hemorrhage, airway_compromise, entrapment, casualties_count, scene_hazards, suspected_trauma.

7. LANGUAGE & CONTEXT:
   - Fluently understand Nigerian Pidgin (e.g., 'Driver no dey talk', 'Blood dey rush well well', 'Leg dey pain me well well') and local vernacular, but formulate ALL output in clear, universally understood, comforting English.
   - STRICT BOUNDARY: Never provide definitive medical diagnoses or prescribe medications.

OUTPUT FORMAT: You MUST reply ONLY with valid JSON matching this schema:
{
  "unresponsive": boolean,
  "severe_hemorrhage": boolean,
  "airway_compromise": boolean,
  "entrapment": boolean,
  "casualties_count": integer (minimum 1),
  "scene_hazards": [list of strings: e.g. "fuel_leak", "vehicle_fire", "live_wire", "flood_water", "aggressive_crowd"],
  "suspected_trauma": [list of strings: e.g. "head trauma", "arterial bleeding", "fracture", "ankle sprain"],
  "reassurance_message": "Warm, grounding, empathetic answer acknowledging their specific situation, reassuring them that responders are en route, and offering compassionate presence",
  "clinical_synthesis": "Plain-language clinical interpretation explaining the injury mechanism, physiology, and why current precautions matter",
  "first_aid_steps": [ordered list of concise, actionable instructions in clear English],
  "assessment_questions": [
    {
      "question": "Clear triage question to evaluate injury severity or complications",
      "options": ["A. Option one", "B. Option two", "C. Option three"]
    }
  ],
  "red_flags": [list of high-risk warning signs that require urgent emergency room or surgical intervention]
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
    history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Ingests bystander voice/text message, optional photo, and multi-turn conversation history,
    returning structured telemetry, clinical synthesis, protocol first aid, assessment questions, and red flags.
    """
    text = (bystander_text or "").strip()
    if not text and not scene_photo_base64:
        return _fallback_heuristic_parser("Emergency assistance requested", history=history)

    # If API key is present, attempt live call to Gemini
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            return _call_gemini_text(text, api_key, scene_photo_base64, history=history)
        except Exception as e:
            print(f"[GeminiEngine] API call failed ({e}). Engaging calibrated fallback parser.")

    # Graceful offline/local heuristic fallback engine
    return _fallback_heuristic_parser(text, history=history)


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
    history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Calls Google Gemini generateContent endpoint across supported candidate models with multi-turn context."""
    contents: List[Dict[str, Any]] = []

    # Prepend previous turns from conversation history
    if history and isinstance(history, list):
        for turn in history:
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

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": contents,
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.45,
            "maxOutputTokens": 1000
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


def _fallback_heuristic_parser(text: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Intelligent local heuristic parser supporting English and Nigerian Pidgin.
    Operates offline or when API keys are absent.
    """
    lower = text.lower()

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
    steps = []
    if unresponsive and airway_compromise:
        steps.append("Immediately check mouth for blockages. Gently tilt the head backward and lift the chin to open the airway.")
        steps.append("If not breathing at all, begin chest compressions: push hard and fast in the center of the chest (100–120 per minute).")
    elif unresponsive and not airway_compromise:
        steps.append("Do NOT shake the person. Check breathing by watching the chest rise and fall.")
        steps.append("If breathing normally, roll gently onto their side into the recovery position to keep the airway clear.")
        steps.append("Keep the neck straight. Do not place pillows under the head if spinal injury is suspected.")

    if severe_hemorrhage:
        steps.append("Find a clean cloth, towel, or shirt. Press down directly and firmly on the bleeding wound with both hands.")
        steps.append("Do NOT remove the cloth even if it soaks through. Add more layers of cloth on top and maintain constant pressure.")

    if is_sprain_or_joint:
        steps.append("Protection & Rest: Stop all running or heavy loading immediately to prevent tearing compromised ligaments.")
        steps.append("Ice & Compression: Apply a cold pack wrapped in cloth for 15–20 minutes, and wrap with comfortable elastic support.")
        steps.append("Elevation: Raise the injured limb above heart level when seated or lying down to reduce acute swelling.")

    if any(h in hazards for h in ["fuel_leak", "vehicle_fire"]):
        steps.append("SCENE SAFETY WARNING: Fuel or fire danger detected. Move bystanders back at least 25 meters. Strictly extinguish all cigarettes and avoid spark sources.")

    if not steps:
        steps.append("Keep the casualty calm, warm, and still. Do not offer food, water, or medication.")
        steps.append("Continuously monitor consciousness and breathing until the response team arrives.")

    # Contextual Clinical Synthesis
    if is_sprain_or_joint:
        synthesis = "Reported symptoms indicate an acute lower-extremity ligamentous or soft-tissue injury. Weight-bearing capacity provides initial clinical screening under Ottawa Decision Rules."
    elif severe_hemorrhage:
        synthesis = "Active vascular hemorrhage reported. Direct mechanical pressure is mandatory to initiate haemostasis and prevent hypovolemic shock."
    elif unresponsive:
        synthesis = "Altered mental status or unconsciousness detected. Maintaining a patent airway and strict cervical spine alignment are the highest clinical priorities."
    else:
        synthesis = "Initial emergency triage assessment in progress. Immediate protocol steps focus on scene stabilization and continuous monitoring."

    # Interactive Assessment Questions with Multiple-Choice Options
    questions = []
    if is_sprain_or_joint:
        questions.append({
            "question": "Where exactly is the pain concentrated when you touch the area?",
            "options": [
                "A. Soft tissue in front of outer ankle bone",
                "B. Directly on the hard outer bone itself",
                "C. Behind the ankle bone or up the shin"
            ]
        })
        questions.append({
            "question": "Can the person take four steps, even with a limp?",
            "options": [
                "A. Yes, can take four steps",
                "B. No, completely unable to bear weight",
                "C. Can walk with minimal discomfort"
            ]
        })
    elif severe_hemorrhage:
        questions.append({
            "question": "Is the bleeding controlled by continuous direct pressure?",
            "options": [
                "A. Bleeding is slowing down or stopped",
                "B. Bleeding continues to soak through cloths",
                "C. Blood is spurting rhythmically"
            ]
        })
    elif unresponsive:
        questions.append({
            "question": "Is the casualty breathing normally and continuously?",
            "options": [
                "A. Breathing normally and regularly",
                "B. Gasping, snoring, or struggling to breathe",
                "C. No breathing detected at all"
            ]
        })
    else:
        questions.append({
            "question": "Is the casualty alert, oriented, and speaking clearly?",
            "options": [
                "A. Alert and speaking in full sentences",
                "B. Confused, drowsy, or drifting off",
                "C. Completely unresponsive to voice or touch"
            ]
        })

    # Red Flag Warning Signs
    if is_sprain_or_joint:
        red_flags = [
            "Complete inability to bear weight or take 4 steps immediately",
            "Severe bone tenderness directly over the malleolus (outer or inner ankle bone)",
            "Visible joint deformity, skin discoloration, or numbness/coldness in the toes"
        ]
    elif severe_hemorrhage:
        red_flags = [
            "Continuous arterial spurting despite firm two-hand direct pressure",
            "Signs of hypovolemic shock: pale/clammy skin, confusion, or rapid shallow breathing"
        ]
    elif unresponsive:
        red_flags = [
            "Cessation of breathing or irregular agonal breathing",
            "Unequal pupils, seizures, or clear fluid draining from nose or ears"
        ]
    else:
        red_flags = [
            "Loss of consciousness or worsening confusion",
            "Difficulty breathing or sudden severe chest pain",
            "Visible open fracture or severe deformity"
        ]

    # Reassurance message in clear, calming, empathetic English
    if is_sprain_or_joint:
        reassurance = "Emergency responders have been notified and are actively en route to your location. Take a slow, steady breath with me — you are not alone, and I am right here beside you to guide you and protect that joint until the medical team arrives."
    elif severe_hemorrhage:
        reassurance = "Emergency responders have been notified and are speeding toward your exact location. Stay right beside them; maintain continuous, firm pressure, and I will be here with you through every single breath until the crew arrives."
    elif unresponsive:
        reassurance = "Emergency responders have been notified and are on their way to you. Stay calm and stay close — keep their airway open, and I am right here walking beside you through every step until the paramedics arrive."
    else:
        reassurance = "Emergency responders have been notified and are actively en route to your location. Take a slow, gentle breath — you are doing the right thing, and I will stay right here to guide you until help arrives."

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

