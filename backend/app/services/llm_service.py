import json
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings


PRE_VISIT_PROMPT = """Analyse these symptoms and return a JSON object with exactly these fields:
- "urgency_level": one of "Low", "Medium", "High"
- "chief_complaint": a short description of the main issue
- "suggested_questions": an array of exactly 3 questions the patient should ask the doctor

Symptoms: {symptoms}

Return ONLY valid JSON, no markdown, no explanation."""

POST_VISIT_PROMPT = """Convert these clinical notes into a patient-friendly summary. Return a JSON object with exactly these fields:
- "diagnosis_explanation": what the diagnosis means in simple terms
- "treatment_plan": what the patient should do
- "medication_instructions": how to take medications
- "follow_up_advice": when to follow up
- "when_to_seek_help": warning signs to watch for

Clinical Notes: {notes}
Prescription: {prescription}

Return ONLY valid JSON, no markdown, no explanation."""


async def call_groq(prompt: str, model: str = None) -> Optional[str]:
    if not settings.GROQ_API_KEY:
        return None

    model = model or settings.GROQ_MODEL
    url = "https://api.groq.com/openai/v1/chat/completions"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Groq API call failed: {e}")
            return None


def parse_json_response(text: str) -> Optional[dict]:
    if not text:
        return None
    try:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def generate_pre_visit_summary(symptoms: str) -> dict:
    prompt = PRE_VISIT_PROMPT.format(symptoms=symptoms)
    raw = await call_groq(prompt)
    parsed = parse_json_response(raw)

    if parsed and all(k in parsed for k in ("urgency_level", "chief_complaint", "suggested_questions")):
        return parsed

    return {
        "urgency_level": "Medium",
        "chief_complaint": "Unable to analyse symptoms at this time",
        "suggested_questions": [
            "What is your diagnosis?",
            "What treatment do you recommend?",
            "When should I follow up?",
        ],
    }


async def generate_post_visit_summary(notes: str, prescription: str) -> dict:
    prompt = POST_VISIT_PROMPT.format(notes=notes, prescription=prescription)
    raw = await call_groq(prompt)
    parsed = parse_json_response(raw)

    if parsed and all(k in parsed for k in (
        "diagnosis_explanation", "treatment_plan",
        "medication_instructions", "follow_up_advice", "when_to_seek_help",
    )):
        return parsed

    return {
        "diagnosis_explanation": "Your doctor has reviewed your case and provided treatment.",
        "treatment_plan": "Follow the prescribed medication and rest as advised.",
        "medication_instructions": f"Take medications as prescribed: {prescription}",
        "follow_up_advice": "Schedule a follow-up if symptoms persist.",
        "when_to_seek_help": "Seek immediate help if symptoms worsen significantly.",
    }
