# ResumeX-v2
An AI-powered resume analyzer and job-matching platform that helps users evaluate their resumes, identify skill gaps, and discover relevant job opportunities.
# ResumeX - AI-Powered Resume Analyzer and Job Matcher

M.Sc. Data Science project. ResumeX reads a PDF resume, shows which technical skills it mentions
and which are missing, and ranks real job listings by how well the resume matches them.

## Features
* **Dashboard**: upload a resume, quick actions, and overview cards (real job count, saved jobs,
  latest analysis). Cards show real session data only; nothing is pre-filled.
* **Resume Analysis**: match score, matched and missing skills, resume quality checks,
  recommendations, a learning roadmap and a downloadable text report.
  Works offline (keyword matching) or with Gemini (optional); falls back to offline if Gemini fails.
* **Job Recommendations**: jobs ranked by the ML matcher, with filters for role, location,
  experience level, job type (internship / full-time), work mode (remote / hybrid / on-site),
  "Real listings only" and "Verified listings only".
* **Saved Jobs**: bookmark jobs during the session.
* **About**: how the score works and what the job data means.

## How the match is calculated (ml_matcher.py)
`score = 0.7 x skill coverage + 0.3 x TF-IDF cosine similarity + 10 if the job title fits the target role`
(capped at 100). It measures what is written in the resume. It is not the probability of being hired
and not a measure of skill level. Jobs whose description has no recognised skill are shown as "Not rated".

## Technology
Python, Streamlit, pandas, scikit-learn (TF-IDF, cosine similarity), pdfplumber,
Google Gemini API via `google-genai` (optional).

## Project files
| File | Purpose |
|---|---|
| `app.py` | Pages and navigation (Streamlit) |
| `ui.py` | CSS and small HTML builders |
| `jobs_utils.py` | Loads and checks `jobs.csv`, ranks, filters |
| `ml_matcher.py` | Skill extraction, TF-IDF job ranking, offline analysis |
| `ai_engine.py` | Optional Gemini analysis and validation |
| `pdf_parser.py` | Text extraction from PDF |
| `jobs.csv` | Job data |

## Install and run locally
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Gemini (optional)
Get a key from Google AI Studio. Use one of:
* Paste it in **Resume Analysis > Optional: use Gemini AI** (kept only in your session), or
* Environment variable: `export GEMINI_API_KEY="your-key"` (Windows: `set GEMINI_API_KEY=your-key`), or
* Streamlit secrets: create `.streamlit/secrets.toml` containing `GEMINI_API_KEY = "your-key"`.

Never commit a key to GitHub. Without a key the offline analysis is used.

## Deploy on Streamlit Community Cloud
1. Push the project folder to a GitHub repository (do not include `secrets.toml`).
2. On share.streamlit.io choose the repository, branch and `app.py` as the main file.
3. Optional: add `GEMINI_API_KEY = "your-key"` under **Settings > Secrets**.

## jobs.csv
Required columns: `title, company, description`. Other columns used by the app:
`url, location, work_mode, experience, exp_level (Fresher / 0-2 years / 2+ years), job_type,
salary, status (verified / demo / unverified), last_verified, link_type (direct / search), notes`.

* `verified` = the posting page was opened on the employer's own hiring page on `last_verified`.
  A vacancy can close at any time; check the page before applying.
* `demo` = sample practice rows with a placeholder company. Their link is a LinkedIn **search**
  page, not an application page. They are hidden by default and ranked separately.
* A row marked verified without a valid link or date is treated as unverified. Unsafe links
  (e.g. `javascript:`) are removed.

To add a real job: open its page, copy title, company and link, list only the skills the posting
actually names in `description`, set `status=verified` and today's date in `last_verified`.

## Changes to the backend (explained)
The 70/30 formula, TF-IDF, whole-word skill matching and the Gemini integration are unchanged.
Targeted fixes: (1) the +10 role bonus needs a real role phrase in the title (e.g. "Data Analyst"),
not one shared word like "engineer"; (2) jobs with no recognised skills are not scored;
(3) more skill spellings and a few extra skills (Excel, NLP, Azure, Spark, ETL, Airflow) and two
extra roles (Data Engineer, Business Intelligence Analyst); (4) empty resume / empty TF-IDF
vocabulary handled; (5) score points exposed so the app can explain each score;
(6) Gemini: prompt treats resume/job text as untrusted data, answer validation is stricter, skills not
in the resume are removed from "matched", clearer error messages.
