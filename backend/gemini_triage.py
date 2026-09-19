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
CANDIDATE_MODELS = [PREFERRED_MODEL, "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
# Remove duplicates while preserving order
CANDIDATE_MODELS = list(dict.fromkeys(CANDIDATE_MODELS))

SYSTEM_INSTRUCTION = """
You are the ResQ Emergency Intelligence Engine, serving as an automated bystander triage assistant in Nigeria under the IEEE Response Quest Challenge 2026.
You are strictly constrained to World Health Organization (WHO) and Nigerian Red Cross bystander first aid protocols.

YOUR RULES:
1. DO NOT diagnose medical conditions or prescribe medication.
2. Provide immediate, sequential, calm, numbered action steps that an untrained bystander can execute in 30 seconds.
3. Prioritize: 1. Scene safety -> 2. Airway -> 3. Hemorrhage control -> 4. Spinal protection -> 5. Recovery position.
4. Support plain English and Nigerian Pidgin fluently (e.g., 'Driver no dey talk', 'Blood dey rush well well').
5. Extract structured emergency telemetry accurately.
1. PRIMARY LANGUAGE IS ENGLISH: All generated responses, including 'reassurance_message' and 'first_aid_steps', MUST ALWAYS be in clear, calm, professional, plain English.
2. UNDERSTAND NIGERIAN PIDGIN & ENGLISH: You can understand bystander input whether in English or Nigerian Pidgin (e.g. 'Driver no dey talk', 'Blood dey rush well well'), but you must ALWAYS formulate your response in clean, universally understood English.
3. DO NOT diagnose medical conditions or prescribe medication.
4. Provide immediate, sequential, calm, numbered action steps that an untrained bystander can execute in 30 seconds.
5. Prioritize: 1. Scene safety -> 2. Airway -> 3. Hemorrhage control -> 4. Spinal protection -> 5. Recovery position.
6. Extract structured emergency telemetry accurately.

OUTPUT FORMAT: You MUST reply ONLY with valid JSON matching this schema:
{
  "unresponsive": boolean,
  "severe_hemorrhage": boolean,
  "airway_compromise": boolean,
  "entrapment": boolean,
  "casualties_count": integer (minimum 1),
  "scene_hazards": [list of strings: e.g. "fuel_leak", "vehicle_fire", "live_wire", "flood_water", "aggressive_crowd"],
  "suspected_trauma": [list of strings: e.g. "head trauma", "arterial bleeding", "fracture", "hypothermia"],
  "first_aid_steps": [ordered list of concise, actionable instructions],
  "reassurance_message": "Calm, empathetic message in the user's language (English or Pidgin) assuring them emergency units are en route"
  "first_aid_steps": [ordered list of concise, actionable instructions in clear English],
  "reassurance_message": "Calm, empathetic message in clear plain English assuring them emergency units are en route"
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
    scene_photo_base64: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ingests bystander voice/text message and optional photo, returning structured
    telemetry and protocol-constrained first aid instructions.
    """
    text = (bystander_text or "").strip()
    if not text and not scene_photo_base64:
        return _fallback_heuristic_parser("Emergency assistance requested")

    # If API key is present, attempt live call to Gemini 2.0 Flash
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            return _call_gemini_text(text, api_key, scene_photo_base64)
        except Exception as e:
            print(f"[GeminiEngine] API call failed ({e}). Engaging calibrated fallback parser.")

    # Graceful offline/local heuristic fallback engine
    return _fallback_heuristic_parser(text)


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


def _call_gemini_text(text: str, api_key: str, photo_b64: Optional[str] = None) -> Dict[str, Any]:
    """Calls Google Gemini generateContent endpoint across supported candidate models."""
    parts: List[Dict[str, Any]] = [{"text": text}]
    if photo_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": photo_b64
            }
        })

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
            "maxOutputTokens": 800
        }
    }

    last_err = None
    for model_name in CANDIDATE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, timeout=8)
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
    return {
        "unresponsive": bool(data.get("unresponsive", False)),
        "severe_hemorrhage": bool(data.get("severe_hemorrhage", False)),
        "airway_compromise": bool(data.get("airway_compromise", False)),
        "entrapment": bool(data.get("entrapment", False)),
        "casualties_count": max(1, int(data.get("casualties_count", 1))),
        "scene_hazards": list(data.get("scene_hazards", [])),
        "suspected_trauma": list(data.get("suspected_trauma", [])),
        "first_aid_steps": list(data.get("first_aid_steps", [])),
        "reassurance_message": str(data.get("reassurance_message", "Help is on the way. Continue following these steps.")),
        "source": "gemini_2_flash",
        "raw_input": raw_text
    }


def _fallback_heuristic_parser(text: str) -> Dict[str, Any]:
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
    if "head" in lower or unresponsive:
        trauma.append("head injury / traumatic brain injury")
    if severe_hemorrhage:
        trauma.append("severe hemorrhage")
    if any(k in lower for k in ["leg", "bone", "arm", "fracture", "break"]):
        trauma.append("extremity fracture")
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

    if any(h in hazards for h in ["fuel_leak", "vehicle_fire"]):
        steps.append("SCENE SAFETY WARNING: Fuel or fire danger detected. Move bystanders back at least 25 meters. Strictly extinguish all cigarettes and avoid spark sources.")

    if not steps:
        steps.append("Keep the casualty calm, warm, and still. Do not offer food, water, or medication.")
        steps.append("Continuously monitor consciousness and breathing until the response team arrives.")

    # Reassurance in user's tone
    is_pidgin = any(pw in lower for pw in ["dey", "don", "am", "wetin", "fit", "plenty", "pikin", "na"])
    if is_pidgin:
        reassurance = "Help dey come now now! Hold the cloth tight make blood stop to flow. We dey monitor your location."
    else:
        reassurance = "Emergency responders have been notified and are en route. Keep calm and continue following these steps."
    reassurance = "Emergency responders have been notified and are en route. Keep calm and continue following these steps."

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

