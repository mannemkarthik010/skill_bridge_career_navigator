import re
from typing import Dict, List, Set

def normalize(text: str) -> str:
    # convert punctuation/slashes/dashes into spaces, keep only a-z0-9 + spaces
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def term_variants(term: str) -> Set[str]:
    t = normalize(term)
    if not t:
        return set()
    toks = t.split()

    variants = {t}
    # join tokens: "ci cd" -> "cicd"
    if len(toks) > 1:
        variants.add("".join(toks))

    return variants

def keyword_extract_skills(resume_text: str, github_text: str, taxonomy: Dict) -> List[str]:
    txt = normalize((resume_text or "") + " " + (github_text or ""))
    found: Set[str] = set()

    for s in taxonomy.get("skills", []):
        name = s["name"]
        syns = [name] + s.get("synonyms", [])
        for term in syns:
            for v in term_variants(term):
                # strict token boundary match in normalized text
                if re.search(rf"(^| )({re.escape(v)})( |$)", txt):
                    found.add(name)
                    break  # stop after first variant match

    return sorted(found)
