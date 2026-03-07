import re
from typing import Dict, List

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()

def compute_gap(profile: Dict, retrieved_chunks: List[Dict], taxonomy: Dict) -> Dict:
    user_skills = set(profile.get("skills", []))

    # Build synonym map for matching skill mentions in job text
    skill_defs = taxonomy.get("skills", [])
    skill_to_terms = {}
    for s in skill_defs:
        name = s["name"]
        terms = [name] + s.get("synonyms", [])
        skill_to_terms[name] = list({_norm(t) for t in terms})

    # Demand scoring: count how many retrieved chunks mention the skill
    demand = {s["name"]: 0 for s in skill_defs}
    evidence = {s["name"]: [] for s in skill_defs}

    for chunk in retrieved_chunks:
        text = _norm(chunk["text"])
        for skill, terms in skill_to_terms.items():
            if any(re.search(rf"(^|[^a-z0-9]){re.escape(t)}([^a-z0-9]|$)", text) for t in terms):
                demand[skill] += 1
                if len(evidence[skill]) < 3:
                    # keep a short evidence snippet
                    raw = chunk["text"].strip().replace("\n", " ")
                    evidence[skill].append(raw[:220] + ("..." if len(raw) > 220 else ""))

    # Identify missing skills with meaningful demand
    missing = []
    for skill, d in demand.items():
        if d >= 2 and skill not in user_skills:
            missing.append({
                "skill": skill,
                "demand_score": d,
                "user_has_skill": False,
                "evidence": evidence[skill]
            })

    missing.sort(key=lambda x: x["demand_score"], reverse=True)

    strengths = [s for s, d in demand.items() if d >= 2 and s in user_skills]

    return {
        "top_missing": missing[:10],
        "strengths": strengths[:20],
        "raw_demand": demand
    }