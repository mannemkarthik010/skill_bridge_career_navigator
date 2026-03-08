import os
import json
import streamlit as st
import re
import requests
from io import BytesIO
from pathlib import Path

from src.extract import extract_profile
from src.embed_store import JobRAG
from src.gap import compute_gap
from src.roadmap import build_roadmap
from src.interview import generate_interview

st.set_page_config(page_title="Skill Bridge – Career Navigator", layout="wide")
def github_username_from_url(url: str) -> str | None:
    if not url:
        return None
    url = url.strip()
    m = re.search(r"github\.com/([^/]+)/?$", url)
    return m.group(1) if m else None


def fetch_github_repos_text(username: str, token: str | None = None, limit: int = 12) -> str:
    """
    Returns a single text blob describing repos for downstream skill extraction.
    Uses GitHub REST API (reliable; no scraping).
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repos = []
    page = 1
    per_page = 100
    while len(repos) < limit:
        r = requests.get(
            f"https://api.github.com/users/{username}/repos",
            params={"per_page": per_page, "page": page, "sort": "updated"},
            headers=headers,
            timeout=20
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1

    # Build a compact “project notes” text
    lines = [f"GitHub projects for {username}:"]
    count = 0
    for repo in repos:
        if repo.get("fork"):
            continue
        name = repo.get("name", "")
        desc = repo.get("description") or ""
        lang = repo.get("language") or ""
        url = repo.get("html_url") or ""
        topics = repo.get("topics") or []
        stars = repo.get("stargazers_count", 0)

        lines.append(f"- Repo: {name}")
        if desc:
            lines.append(f"  Description: {desc}")
        if lang:
            lines.append(f"  Primary language: {lang}")
        if topics:
            lines.append(f"  Topics: {', '.join(topics)}")
        lines.append(f"  Stars: {stars}")
        lines.append(f"  URL: {url}")
        lines.append("")

        count += 1
        if count >= limit:
            break

    return "\n".join(lines).strip()


def read_uploaded_resume(file) -> str:
    """
    Supports txt/docx/pdf.
    """
    name = (file.name or "").lower()

    if name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")

    if name.endswith(".docx"):
        from docx import Document
        doc = Document(file)
        return "\n".join(p.text for p in doc.paragraphs)

    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(file.read()))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    return ""

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
    st.warning(
        "OPENAI_API_KEY is not set. The app will still work: "
        "resume parsing + skill extraction + job retrieval run locally (TF-IDF fallback). "
        "Interview/roadmap narration will be simpler."
    )

col1, col2 = st.columns(2)

with col1:
    st.subheader("Resume")
    uploaded_resume = st.file_uploader("Upload resume (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
    resume_text_paste = st.text_area("Or paste resume text", height=200, placeholder="Paste your resume here...")

    resume_text_upload = read_uploaded_resume(uploaded_resume) if uploaded_resume else ""
    resume_text = (resume_text_upload.strip() + "\n\n" + resume_text_paste.strip()).strip()

    if uploaded_resume and resume_text_upload.strip():
        st.caption(f"Parsed text from: {uploaded_resume.name} ({len(resume_text_upload)} chars)")

with col2:
    st.subheader("GitHub")
    github_url = st.text_input("GitHub profile URL (optional)", placeholder="https://github.com/<username>")
    st.caption("Tip: set GITHUB_TOKEN in Streamlit secrets to avoid GitHub API rate limits.")

    # If user pasted “GitHub-like text”, keep it too
    github_text_manual = st.text_area(
        "Optional: paste README snippets / project notes",
        height=200,
        placeholder="Paste README snippets, project summaries, tech stack, etc..."
    )

    github_text = github_text_manual.strip()

    user = github_username_from_url(github_url) if github_url else None
    if github_url:
        st.link_button("Open GitHub Profile", github_url)

    # Auto-fetch projects and append to github_text
    if user and st.button("Fetch GitHub Projects"):
        try:
            gh_token = st.secrets.get("GITHUB_TOKEN", None)
            fetched = fetch_github_repos_text(user, token=gh_token, limit=12)
            # Store fetched results in session so it persists
            st.session_state["github_fetched_text"] = fetched
            st.success(f"Fetched projects for {user}.")
        except Exception as e:
            st.error(f"Failed to fetch GitHub repos: {e}")

    fetched_text = st.session_state.get("github_fetched_text", "")
    if fetched_text:
        st.caption("Using fetched GitHub projects text for analysis.")

        with st.expander("Show fetched GitHub projects"):
            st.text(fetched_text)  # or st.code(fetched_text)

        github_text = (github_text + "\n\n" + fetched_text).strip()
st.divider()

@st.cache_resource
def load_taxonomy():
    # Prefer ./data/*, fall back to repo root for easier local runs.
    here = Path(__file__).parent
    p = here / "data" / "skill_taxonomy.json"
    if not p.exists():
        p = here / "skill_taxonomy.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_resource
def load_resources():
    here = Path(__file__).parent
    p = here / "data" / "resources.json"
    if not p.exists():
        p = here / "resources.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

taxonomy = load_taxonomy()
resources = load_resources()

def role_to_job_file(r: str) -> str:
    if r == "Cloud Engineer":
        return str((Path(__file__).parent / "data" / "jobs_cloud.jsonl").resolve())
    if r == "Data Analyst":
        return str((Path(__file__).parent / "data" / "jobs_data.jsonl").resolve())
    return str((Path(__file__).parent / "data" / "jobs_security.jsonl").resolve())

def _fallback_job_file_if_missing(p: str) -> str:
    # If running without a data/ folder, use repo-root files
    path = Path(p)
    if path.exists():
        return str(path)
    here = Path(__file__).parent
    alt = here / path.name
    return str(alt)

@st.cache_resource
def load_rag(job_file: str):
    rag = JobRAG(job_file=job_file)
    rag.build_or_load()
    return rag

job_file = role_to_job_file(role)
job_file = _fallback_job_file_if_missing(job_file)
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
        gap = compute_gap(
            profile=profile,
            retrieved_chunks=retrieved,
            taxonomy=taxonomy,
            resume_text=resume_text,
            github_text=github_text,
        )

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
            st.markdown(f"**{item['skill']}**")
            st.write(f"- Demand score: `{item['demand_score']}` | You: `{item.get('user_level','missing')}`")
            if item.get("user_evidence"):
                st.caption("Evidence from your resume/projects:")
                for ue in item["user_evidence"][:2]:
                    st.markdown(f"> {ue}")
            st.caption("Evidance from job postings:")
            for ev in item.get("evidence", [])[:2]:
                st.markdown(f"> {ev}")
            
        st.subheader("Exposure skills (turn into proof projects)")
        for item in gap.get("top_exposure", []):
            st.markdown(f"### {item['skill']}")
            st.write(f"Demand score: {item['demand_score']} | You: {item.get('user_level','exposure')}")
            if item.get("user_evidence"):
                st.caption("Evidence from your resume/projects:")
                for ue in item["user_evidence"][:2]:
                    st.markdown(f"> {ue}")
            st.caption("What to do next:")
            st.markdown("- Build a mini-project and add it to GitHub + resume bullets.")
        

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
