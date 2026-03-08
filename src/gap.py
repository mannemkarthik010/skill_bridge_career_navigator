import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ValidationError

from src.fallback import keyword_extract_skills

# OpenAI SDK (v1+)
from openai import OpenAI

class ProfileSchema(BaseModel):
    target_role: str
    skills: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    notes: str = ""

def _llm_extract(resume_text: str, github_text: str, target_role: str, taxonomy: Dict, api_key: str) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)
    skill_names = [s["name"] for s in taxonomy.get("skills", [])]

    system = (
        "You extract structured career profile data from resume and project text. "
        "Return ONLY valid JSON matching the schema. Do not add extra keys."
    )

    user = {
        "target_role": target_role,
        "resume_text": resume_text[:12000],
        "github_text": github_text[:12000],
        "allowed_skills": skill_names
    }

    schema_hint = {
        "target_role": "string",
        "skills": ["string skill from allowed_skills"],
        "projects": ["short project bullet"],
        "notes": "1-2 sentences about seniority/strengths"
    }

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Input:\n{json.dumps(user)}\n\nSchema:\n{json.dumps(schema_hint)}"}
        ],
        temperature=0.2
    )
    text = resp.choices[0].message.content.strip()
    data = json.loads(text)
    # validate schema strictly
    parsed = ProfileSchema(**data).model_dump()
    # enforce allowed skills
    parsed["skills"] = [s for s in parsed["skills"] if s in skill_names]
    return parsed

def extract_profile(resume_text: str, github_text: str, target_role: str, taxonomy: Dict, openai_api_key: str) -> Dict[str, Any]:
    # Try LLM
    if openai_api_key:
        try:
            return _llm_extract(resume_text, github_text, target_role, taxonomy, openai_api_key)
        except (ValidationError, json.JSONDecodeError, Exception):
            pass

    # Fallback keyword extraction
    skills = keyword_extract_skills(resume_text, github_text, taxonomy)
    return {
        "target_role": target_role,
        "skills": skills,
        "projects": [],
        "notes": "Fallback extraction used (keyword-based). Add richer project text for better results."
    }
