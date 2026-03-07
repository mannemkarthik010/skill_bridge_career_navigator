import re
from typing import Dict, List, Set

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def keyword_extract_skills(resume_text: str, github_text: str, taxonomy: Dict) -> List[str]:
    txt = normalize((resume_text or "") + " " + (github_text or ""))
    found: Set[str] = set()

    # taxonomy format: {"skills": [{"name": "...", "synonyms": [...]}, ...]}
    for s in taxonomy.get("skills", []):
        name = s["name"]
        syns = [name] + s.get("synonyms", [])
        for term in syns:
            term_n = normalize(term)
            # word-boundary-ish match
            if re.search(rf"(^|[^a-z0-9]){re.escape(term_n)}([^a-z0-9]|$)", txt):
                found.add(name)

    return sorted(found)