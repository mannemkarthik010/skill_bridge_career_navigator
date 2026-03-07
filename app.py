import os
import json
import streamlit as st

from src.extract import extract_profile
from src.embed_store import JobRAG
from src.gap import compute_gap
from src.roadmap import build_roadmap
from src.interview import generate_interview

st.set_page_config(page_title="Skill Bridge – Career Navigator", layout="wide")

st.title("Skill Bridge – Career Navigator")
st.caption("Paste a resume + GitHub-like project notes → get a gap dashboard, roadmap, and mock interview set.")

with st.sidebar:
    st.header("Settings")
    role = st.selectbox("Target role", ["Cloud Engineer", "Data Analyst", "Cybersecurity Analyst"])
    time_per_week = st.slider("Hours per week", min_value=2, max_value=40, value=10, step=1)
    budget = st.selectbox("Budget", ["Free only", "Mostly free", "Any (paid allowed)"])
    k_retrieval = st.slider("RAG: number of job chunks to retrieve", min_value=5, max_value=30, value=12, step=1)

api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not api_key:
    st.warning("OPENAI_API_KEY is not set. The app will still work using fallback extraction, but interview/roadmap narration will be simpler.")

col1, col2 = st.columns(2)
with col1:
    resume_text = st.text_area("Resume text", height=260, placeholder="Paste your resume here...")
with col2:
    github_text = st.text_area("GitHub-like project input (optional)", height=260, placeholder="Paste README snippets, project summaries, tech stack, etc...")

st.divider()

@st.cache_resource
def load_taxonomy():
    with open("data/skill_taxonomy.json", "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_resource
def load_resources():
    with open("data/resources.json", "r", encoding="utf-8") as f:
        return json.load(f)

taxonomy = load_taxonomy()
resources = load_resources()

def role_to_job_file(r: str) -> str:
    if r == "Cloud Engineer":
        return "data/jobs_cloud.jsonl"
    if r == "Data Analyst":
        return "data/jobs_data.jsonl"
    return "data/jobs_security.jsonl"

@st.cache_resource
def load_rag(job_file: str):
    rag = JobRAG(job_file=job_file)
    rag.build_or_load()
    return rag

job_file = role_to_job_file(role)
rag = load_rag(job_file)

if st.button("Analyze Gap", type="primary"):
    if not resume_text.strip() and not github_text.strip():
        st.error("Please paste at least resume text (or GitHub-like text).")
        st.stop()

    with st.spinner("Extracting skills (LLM + fallback)..."):
        profile = extract_profile(
            resume_text=resume_text,
            github_text=github_text,
            target_role=role,
            taxonomy=taxonomy,
            openai_api_key=api_key
        )

    st.session_state["profile"] = profile

    with st.spinner("Retrieving relevant job requirements (RAG)..."):
        retrieved = rag.retrieve(query=f"{role} responsibilities requirements skills", k=k_retrieval)

    st.session_state["retrieved_jobs"] = retrieved

    with st.spinner("Computing skill gaps..."):
        gap = compute_gap(profile=profile, retrieved_chunks=retrieved, taxonomy=taxonomy)

    st.session_state["gap"] = gap

if "gap" in st.session_state:
    profile = st.session_state["profile"]
    gap = st.session_state["gap"]
    retrieved = st.session_state["retrieved_jobs"]

    left, right = st.columns([1.2, 1.0])

    with left:
        st.subheader("Gap Analysis Dashboard")
        st.write("**Detected skills:**", ", ".join(sorted(profile["skills"])) if profile["skills"] else "None detected")

        st.markdown("### Top missing skills")
        for item in gap["top_missing"]:
            st.markdown(f"**{item['skill']}**  \n"
                        f"- Demand score: `{item['demand_score']}` | You: `{item['user_has_skill']}`")
            if item.get("evidence"):
                st.caption("Evidence from job postings:")
                for ev in item["evidence"][:2]:
                    st.markdown(f"> {ev}")

        st.markdown("### Transferable strengths")
        if gap["strengths"]:
            st.write(", ".join(gap["strengths"][:20]))
        else:
            st.write("No strong transferable skills detected yet (this improves with richer resume/project text).")

    with right:
        st.subheader("Next Steps Roadmap")
        roadmap = build_roadmap(
            role=role,
            gap=gap,
            resources=resources,
            hours_per_week=time_per_week,
            budget=budget,
            openai_api_key=api_key,
            profile=profile
        )
        st.session_state["roadmap"] = roadmap

        for week in roadmap["weeks"]:
            st.markdown(f"### {week['title']}")
            for step in week["steps"]:
                st.markdown(f"- {step}")

        st.divider()
        st.subheader("Mock Interview Pivot")
        interview = generate_interview(
            role=role,
            profile=profile,
            gap=gap,
            openai_api_key=api_key
        )
        st.session_state["interview"] = interview

        for section in interview["sections"]:
            st.markdown(f"### {section['title']}")
            for q in section["questions"]:
                st.markdown(f"- {q}")

    st.divider()
    with st.expander("Debug: extracted profile JSON"):
        st.json(profile)
    with st.expander("Debug: retrieved job chunks"):
        st.write([x["text"][:300] + "..." for x in retrieved[:5]])