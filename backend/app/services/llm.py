"""LLM Service for analyzing patient symptoms."""

import os
import json
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Prompt template requested by the user
PROMPT_TEMPLATE = """Analyse these symptoms and return: urgency level (Low / Medium / High), chief complaint, and three suggested questions for the doctor. Symptoms: <{symptoms}>"""

async def analyze_symptoms_with_llm(symptoms: str, retry: bool = True) -> dict:
    """
    Calls the Gemini LLM to analyze symptoms.
    Returns a dict with:
        - urgency_level
        - chief_complaint
        - suggested_questions
        - raw_llm_response
    """
    api_key = settings.LLM_API_KEY
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        logger.warning("No valid LLM_API_KEY found. Falling back to default parser.")
        return _fallback_response(symptoms)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    prompt = PROMPT_TEMPLATE.format(symptoms=symptoms)
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    raw_response_text = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            
            data = res.json()
            # Extract text from Gemini response
            raw_response_text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Parse the strict JSON
            parsed = json.loads(raw_response_text)
            
            return {
                "urgency_level": parsed.get("urgency_level", "Unknown"),
                "chief_complaint": parsed.get("chief_complaint", symptoms),
                "suggested_questions": parsed.get("suggested_questions", []),
                "raw_llm_response": raw_response_text
            }
            
    except Exception as e:
        logger.error(f"LLM Call failed: {str(e)}")
        if retry:
            logger.info("Retrying LLM call once...")
            return await analyze_symptoms_with_llm(symptoms, retry=False)
        
        # Fallback exactly as requested: raw_llm_response=null, chief_complaint=raw text, urgency_level='Unknown'
        return _fallback_response(symptoms)

def _fallback_response(symptoms: str) -> dict:
    return {
        "urgency_level": "Unknown",
        "chief_complaint": symptoms,
        "suggested_questions": [],
        "raw_llm_response": None
    }


POST_VISIT_PROMPT = """Convert these clinical notes into a patient-friendly summary with medication schedule and follow-up steps: <{notes}>"""

async def generate_patient_friendly_summary(notes: str, retry: bool = True) -> str:
    """
    Calls the Gemini LLM to convert clinical notes into a patient-friendly summary.
    Gracefully falls back to the raw notes if the API fails.
    """
    api_key = settings.LLM_API_KEY
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        logger.warning("No valid LLM_API_KEY found. Falling back to raw notes.")
        return notes

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    prompt = POST_VISIT_PROMPT.format(notes=notes)
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            
            data = res.json()
            # Extract text from Gemini response
            summary_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return summary_text
            
    except Exception as e:
        logger.error(f"LLM Call failed for post-visit: {str(e)}")
        if retry:
            logger.info("Retrying post-visit LLM call once...")
            return await generate_patient_friendly_summary(notes, retry=False)
        
        # Fallback exactly as requested: return raw notes
        return notes
