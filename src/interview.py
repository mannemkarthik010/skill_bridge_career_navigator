from typing import Dict, Any, List
from openai import OpenAI

def generate_interview(role: str, profile: Dict, gap: Dict, openai_api_key: str) -> Dict[str, Any]:
    missing = [x["skill"] for x in gap.get("top_missing", [])][:6]
    strengths = gap.get("strengths", [])[:6]

    # Fallback questions (no API key)
    if not openai_api_key:
        return {
            "sections": [
                {"title": "Core role questions", "questions": [
                    f"Explain a typical day-in-the-life of a {role}. What tools do you use and why?",
                    "Walk through one of your projects end-to-end: requirements → design → implementation → testing → deployment."
                ]},
                {"title": "Gap-focused questions", "questions": [f"What is {s}? Where would you use it?" for s in missing]},
                {"title": "Strength questions", "questions": [f"Deep dive: {s} — explain a real scenario where you used it." for s in strengths]},
            ]
        }

    # LLM-generated, tailored questions
    client = OpenAI(api_key=openai_api_key)
    payload = {
        "role": role,
        "user_skills": profile.get("skills", []),
        "missing_skills": missing,
        "projects": profile.get("projects", []),
    }

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[
            {"role": "system", "content": "Generate interview questions. Return JSON only: {sections:[{title:string, questions:[string]}]}."},
            {"role": "user", "content": str(payload)}
        ]
    )

    import json
    try:
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        return {
            "sections": [
                {"title": "Gap-focused questions", "questions": [f"Explain {s} and how it fits into {role} work." for s in missing]}
            ]
        }