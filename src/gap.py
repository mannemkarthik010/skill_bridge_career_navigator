import re
from typing import Dict, List, Tuple

def _norm(s: str) -> str:
    """Lowercase + collapse whitespace. (keeps punctuation for boundary regex)"""
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def _find_term_hits(text: str, terms: List[str], max_snips: int = 2) -> Tuple[int, List[str]]:
    """Count term mentions and return a few user-facing snippets."""
    if not text:
        return 0, []
    txt = _norm(text)

    count = 0
    snippets: List[str] = []

    for t in terms:
        pattern = rf"(^|[^a-z0-9]){re.escape(t)}([^a-z0-9]|$)"
        for m in re.finditer(pattern, txt):
            count += 1
            if len(snippets) < max_snips:
                start = max(0, m.start() - 60)
                end = min(len(txt), m.end() + 60)
                snippets.append(txt[start:end].strip())
        if count >= 3 and len(snippets) >= max_snips:
            break

    return count, snippets

def compute_gap(
    profile: Dict,
    retrieved_chunks: List[Dict],
    taxonomy: Dict,
    resume_text: str = "",
    github_text: str = "",
) -> Dict:
    user_skills = set(profile.get("skills", []))

    # Build synonym map
    skill_defs = taxonomy.get("skills", [])
    skill_to_terms = {}
    for s in skill_defs:
        name = s["name"]
        terms = [name] + s.get("synonyms", [])
        skill_to_terms[name] = list({_norm(t) for t in terms})

    # Demand scoring (job-side)
    demand = {s["name"]: 0 for s in skill_defs}
    evidence = {s["name"]: [] for s in skill_defs}

    for chunk in retrieved_chunks:
        text = _norm(chunk["text"])
        for skill, terms in skill_to_terms.items():
            if any(re.search(rf"(^|[^a-z0-9]){re.escape(t)}([^a-z0-9]|$)", text) for t in terms):
                demand[skill] += 1
                if len(evidence[skill]) < 3:
                    raw = chunk["text"].strip().replace("\n", " ")
                    evidence[skill].append(raw[:220] + ("..." if len(raw) > 220 else ""))

    # --- 2.1 User evidence scoring (resume/github-side) ---
    user_text = (resume_text or "") + "\n" + (github_text or "")
    user_hits: Dict[str, int] = {}
    user_snips: Dict[str, List[str]] = {}
    user_level: Dict[str, str] = {}

    for skill, terms in skill_to_terms.items():
        hits, snips = _find_term_hits(user_text, terms, max_snips=2)
        user_hits[skill] = hits
        user_snips[skill] = snips

        if hits >= 2:
            user_level[skill] = "strong"
        elif hits == 1:
            user_level[skill] = "exposure"
        else:
            user_level[skill] = "missing"

    # Missing skills (job demand + user missing)
    missing = []
    exposure = []
    
    for skill, d in demand.items():
        if d < 2:
            continue  # not in-demand enough

        # evidence-based labels (preferred)
        lvl = user_level.get(skill, "missing")

        item = {
            "skill": skill,
            "demand_score": d,
            "user_level": lvl,
            "user_evidence": user_snips.get(skill, []),
            "evidence": evidence[skill],
        }

        if (resume_text or github_text):
            if lvl == "missing":
                missing.append(item)
            elif lvl == "exposure":
                exposure.append(item)
            # if strong, ignore here (it’s a strength)
        else:
            # old behavior fallback if no text provided
            if skill not in user_skills:
                missing.append(item)

    missing.sort(key=lambda x: x["demand_score"], reverse=True)
    exposure.sort(key=lambda x: x["demand_score"], reverse=True)

    # Strengths: demanded + strong evidence (fallback to old behavior if no text)
    if (resume_text or github_text):
        strengths = [s for s, d in demand.items() if d >= 2 and user_level.get(s) == "strong"]
    else:
        strengths = [s for s, d in demand.items() if d >= 2 and s in user_skills]

    return {
    "top_missing": missing[:10],
    "top_exposure": exposure[:10],
    "strengths": strengths[:20],
    "raw_demand": demand,
    "user_levels": user_level,
    "user_hits": user_hits }
