import os
from typing import Dict, Any, List
from openai import OpenAI

def _basic_plan(gap: Dict, resources: Dict, hours_per_week: int, budget: str) -> Dict[str, Any]:
    missing = [x["skill"] for x in gap.get("top_missing", [])][:6]
    weeks = []
    # 2-week plan for speed
    split = [missing[:3], missing[3:6]]

    for i, bucket in enumerate(split, start=1):
        steps = []
        for skill in bucket:
            recs = resources.get(skill, [])
            # pick 1-2 best
            for r in recs[:2]:
                if budget == "Free only" and r.get("type") == "paid":
                    continue
                steps.append(f"{skill}: {r['title']} ({r['provider']}) – {r['url']}")
                if r.get("project"):
                    steps.append(f"Mini-project: {r['project']}")
                break
        weeks.append({"title": f"Week {i}", "steps": steps or ["No resources found for these skills. Add to resources.json."]})

    return {"weeks": weeks, "skills_targeted": missing}

def build_roadmap(role: str, gap: Dict, resources: Dict, hours_per_week: int, budget: str, openai_api_key: str, profile: Dict) -> Dict[str, Any]:
    plan = _basic_plan(gap, resources, hours_per_week, budget)

    if not openai_api_key:
        return plan

    # Optional: have LLM rewrite steps into clearer milestones (but keep same content)
    try:
        client = OpenAI(api_key=openai_api_key)
        prompt = {
            "role": role,
            "hours_per_week": hours_per_week,
            "budget": budget,
            "target_skills": plan["skills_targeted"],
            "draft_plan": plan["weeks"],
            "user_skills": profile.get("skills", [])
        }
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=[
                {"role": "system", "content": "Rewrite the roadmap steps to be clearer and outcome-focused. Keep links intact. Return JSON: {weeks:[{title,steps:[...]}]} only."},
                {"role": "user", "content": str(prompt)}
            ]
        )
        out = resp.choices[0].message.content.strip()
        # Best-effort parse
        import json
        obj = json.loads(out)
        if "weeks" in obj:
            return {"weeks": obj["weeks"], "skills_targeted": plan["skills_targeted"]}
    except Exception:
        pass

    return plan