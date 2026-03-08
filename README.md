# Skill Bridge – Evidence-Driven Career Navigator  
**Palo Alto Networks – New Grad SWE Take-Home Case Study**

---

## Candidate Name
Your Name

## Scenario Chosen
Skill-Bridge Career Navigator

## Estimated Time Spent
~5–6 hours

---

## Quick Links (Design Diagrams)
- **System Architecture Diagram**
- **Hybrid Profile Extraction Diagram**
- **Data Flow Diagram**
- **RAG Architecture Diagram**

> Note: The diagrams below are included as **PNG files** in this repo for quick reviewer scanning.

---

# 1. Overview

Skill Bridge is a modular, evidence-driven career intelligence system that:
- Parses synthetic resume + GitHub-like input
- Retrieves relevant job requirements from a local synthetic dataset
- Computes demand-weighted, explainable skill gaps
- Generates a time/budget-aware learning roadmap
- Produces mock interview questions grounded in the gap output

This project prioritizes **engineering behavior** (requirements, validation, edge cases, testing, and tradeoffs) over UI polish.

---

# 2. Diagrams

## 2.1 System Architecture Diagram
![System Architecture](docs/diagrams/architecture.png)

**What this shows:**  
High-level module boundaries and how data moves from user inputs → intelligence pipeline → outputs.

---

## 2.2 Hybrid Profile Extraction Diagram (AI + Fallback)
![Hybrid Profile Extraction](docs/diagrams/hybrid_profile_extraction.png)

**What this shows (technical):**
- Primary path: LLM-based structured extraction returning schema-constrained JSON
- Validation: strict schema parsing + taxonomy filtering
- Fallback path: deterministic keyword extraction (token-boundary matching) when AI is unavailable or incorrect

---

## 2.3 Data Flow Diagram (DFD)
![Data Flow Diagram](docs/diagrams/data_flow.png)

**What this shows:**  
Processes and data stores end-to-end (resume parsing → extraction → retrieval → gap scoring → roadmap/interview → UI), including the synthetic datasets and configuration stores.

---

## 2.4 RAG Architecture Diagram
![RAG Architecture](docs/diagrams/rag_architecture.png)

**What this shows (technical):**
- Job dataset ingestion (JSONL)
- Chunking strategy
- Embedding generation
- FAISS indexing and top-K retrieval
- Retrieved chunks feeding the deterministic gap engine

---

# 3. Core Flow (End-to-End)

1. User uploads resume (PDF/DOCX/TXT) and optionally adds GitHub URL / project notes  
2. System parses and validates input text  
3. Profile extraction runs (AI → schema validation → taxonomy filtering → fallback if needed)  
4. Job requirement retrieval runs over synthetic job dataset  
5. Gap engine computes demand-weighted missing/exposure/strength skills with evidence snippets  
6. Roadmap generator maps gaps → curated resources + mini-projects (budget/time aware)  
7. Interview generator produces gap-focused and strength deep-dive questions  
8. Streamlit UI renders dashboard outputs

---

# 4. AI Integration + Deterministic Fallback

## Primary AI Capability: Structured Profile Extraction
The system attempts to extract a structured profile object:
- `target_role`
- `skills[]` (constrained to taxonomy)
- `projects[]`
- `notes`

### Reliability Controls
- Strict schema validation (rejects malformed or extra keys)
- Skill list filtered to the allowed taxonomy (prevents hallucinated skills)
- If AI is unavailable/incorrect → deterministic fallback keyword extraction executes

AI is used **assistively**; final decisions (gap scoring) remain deterministic for reproducibility and explainability.

---

# 5. Gap Analysis Engine (Demand-Weighted & Explainable)

The gap engine is intentionally deterministic:

**Inputs**
- Extracted profile (skills)
- Top-K retrieved job chunks
- Skill taxonomy (name + synonyms)
- Resume + GitHub text corpus

**Core Logic**
- **Demand score**: counts how often each skill appears in retrieved job chunks  
- **User evidence**: counts mentions in resume/GitHub text with snippets  
- Classifies skills as:
  - **Strong** (≥2 mentions)
  - **Exposure** (1 mention)
  - **Missing** (0 mentions)
- Filters low-signal skills (e.g., demand < 2)
- Ranks missing/exposure by demand score
- Returns evidence snippets from both job side and user side to keep outputs explainable

---

# 6. Data Safety & Security

- Uses **synthetic datasets only** (no real personal data)
- Does **not** scrape live sites
- Does **not** commit API keys
- Uses `.env` for secrets + includes `.env.example`

---

# 7. Testing (Basic Quality)

At least two tests are included:
- **Happy path**: valid input produces a profile + gap output structure
- **Edge case**: empty/malformed input (or malformed AI response) triggers fallback or error handling

Focus is on correctness under normal and degraded conditions.

---

# 8. Tradeoffs & Prioritization

Given the 4–6 hour timebox, I prioritized:
- Clear modular design
- Deterministic + explainable scoring
- AI fallback reliability
- Input validation and clear error handling
- Basic tests (happy path + edge case)

Intentionally cut for time:
- Production deployment + auth
- Real-time ingestion/scraping
- Advanced ranking heuristics
- Full test suite coverage

---

# 9. Future Improvements

- Skill seniority weighting (junior vs senior requirements)
- Periodic index refresh pipeline for job datasets
- Improved evaluation metrics for roadmap effectiveness
- CI workflow (lint + tests) to enforce quality gates
- Expanded tests and property-based edge case coverage

---

# 10. Quick Start

## Prerequisites
- Python 3.10+
- pip

## Setup
```bash
git clone <repo>
cd skill-bridge
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
