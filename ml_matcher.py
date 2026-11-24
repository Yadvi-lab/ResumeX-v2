# ml_matcher.py
"""Offline job matching and skill-gap analysis (no internet or API needed).

Method (unchanged from the original project):
  * Skills are found with whole-word matching, so "java" is NOT found inside
    "javascript".
  * Job score = 70% skill coverage + 30% TF-IDF cosine similarity
    (+10 if the job title fits the chosen role), capped at 100.

Targeted corrections made in version 2 (the formula and weights are the same):
  1. The +10 role bonus now needs a real role phrase in the job title
     (e.g. "Data Analyst"), not just one shared word such as "engineer".
  2. A job whose description contains no recognised skill is flagged
     scored=False and gets no score, instead of a score made only of text
     similarity.
  3. More skill spellings (e.g. "power-bi", "python3") and a few extra skills
     (Excel, NLP, Azure, Spark, ETL, Airflow). Line breaks and double spaces
     inside a skill name ("machine\\nlearning") are handled.
  4. An empty resume or an empty TF-IDF vocabulary no longer crashes.
  5. Each job row also carries the points behind its score, so the app can
     explain it (skill_points + text_points + bonus_points).
  6. load_jobs() trims blanks and removes duplicate rows.
"""
import os
import re

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(BASE_DIR, "jobs.csv")

# display name -> accepted spellings (lower case)
SKILLS = {
    "Python": ["python", "python3"],
    "Java": ["java"],
    "C++": ["c++", "cpp"],
    "SQL": ["sql"],
    "JavaScript": ["javascript", "java script", "ecmascript"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "reactjs", "react.js", "react js"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi", "fast api"],
    "Django": ["django"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn", "sci-kit learn"],
    "Machine Learning": ["machine learning", "machine-learning"],
    "Deep Learning": ["deep learning", "deep-learning"],
    "PyTorch": ["pytorch", "py torch"],
    "TensorFlow": ["tensorflow", "tensor flow"],
    "Statistics": ["statistics", "statistical", "statistic"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi", "power-bi"],
    "Git": ["git", "github", "gitlab", "bitbucket"],
    "Docker": ["docker"],
    "AWS": ["aws", "amazon web services"],
    "PostgreSQL": ["postgresql", "postgres", "postgre sql"],
    "MySQL": ["mysql", "my sql"],
    "MongoDB": ["mongodb", "mongo db"],
    "REST APIs": ["rest api", "rest apis", "restful", "rest-api"],
    "Data Structures": ["data structures", "data structure", "dsa"],
    "Algorithms": ["algorithms", "algorithm"],
    # Added in version 2 (common in data / fresher job postings):
    "Excel": ["excel", "ms excel", "microsoft excel"],
    "NLP": ["nlp", "natural language processing"],
    "Azure": ["azure", "microsoft azure"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "ETL": ["etl", "data pipeline", "data pipelines"],
    "Airflow": ["airflow", "apache airflow"],
}

# Core skills expected for each target role (used by the benchmark mode).
ROLE_PROFILES = {
    "Software Engineer": [
        "Python", "Java", "Data Structures", "Algorithms",
        "Git", "SQL", "Docker", "REST APIs",
    ],
    "Data Scientist / Analyst": [
        "Python", "SQL", "Pandas", "NumPy",
        "Statistics", "Machine Learning", "scikit-learn", "Tableau",
    ],
    "Backend Developer (Python)": [
        "Python", "Flask", "FastAPI", "SQL",
        "REST APIs", "Docker", "Git", "AWS",
    ],
    "Frontend Developer": [
        "JavaScript", "HTML", "CSS", "React", "Git", "REST APIs",
    ],
    "AI / ML Engineer": [
        "Python", "Machine Learning", "Deep Learning", "PyTorch",
        "TensorFlow", "scikit-learn", "NumPy", "Pandas",
    ],
    # Added in version 2:
    "Data Engineer": [
        "Python", "SQL", "ETL", "Spark", "PostgreSQL", "AWS", "Docker", "Git",
    ],
    "Business Intelligence Analyst": [
        "SQL", "Power BI", "Tableau", "Excel", "Statistics", "Python",
    ],
}

# CHANGED: a job title "fits" a role only if it contains one of these phrases.
# The original used single shared words ("engineer", "developer", "data"),
# so unrelated titles such as "Data Engineer" got the Software Engineer bonus.
ROLE_TITLE_PATTERNS = {
    "Software Engineer": r"\b(software|full[- ]?stack|back[- ]?end|front[- ]?end|java|python)"
                         r"\s+(\w+\s+)?(engineer|developer)\b|\bsde\b|\bprogrammer\b",
    "Data Scientist / Analyst": r"\bdata (scientist|analyst|analytics)\b|\bbusiness intelligence\b"
                                r"|\bbi (analyst|developer)\b",
    "Backend Developer (Python)": r"\bback[- ]?end\b|\bpython\s+(\w+\s+)?(developer|engineer)\b"
                                  r"|\bfull[- ]?stack\b|\bdjango\b|\bflask\b|\bfastapi\b",
    "Frontend Developer": r"\bfront[- ]?end\b|\breact\b|\bui (developer|engineer)\b"
                          r"|\bweb developer\b|\bfull[- ]?stack\b",
    "AI / ML Engineer": r"\b(ai|ml)\b|\bmachine learning\b|\bdeep learning\b"
                        r"|\bartificial intelligence\b",
    "Data Engineer": r"\bdata engineer(ing)?\b|\betl\b|\bdata platform\b|\bdata pipeline",
    "Business Intelligence Analyst": r"\bbusiness intelligence\b|\bbi (analyst|developer|engineer)\b"
                                     r"|\bpower bi\b|\bdata analyst\b|\banalytics\b|\breporting analyst\b",
}
_ROLE_REGEX = {role: re.compile(p) for role, p in ROLE_TITLE_PATTERNS.items()}


def title_fits_role(title: str, role: str) -> bool:
    """True if the job title contains a phrase that belongs to the role."""
    regex = _ROLE_REGEX.get(role)
    return bool(regex and regex.search(str(title).lower()))


def _pattern(alias: str) -> re.Pattern:
    # The alias must not be glued to other letters/digits/+/# on either side.
    return re.compile(r"(?<![a-z0-9+#])" + re.escape(alias) + r"(?![a-z0-9+#])")


_PATTERNS = {
    name: [_pattern(a) for a in aliases] for name, aliases in SKILLS.items()
}


def find_skills(text: str) -> list:
    """Return the display names of all known skills mentioned in text."""
    lowered = str(text).lower()
    # CHANGED: PDF line breaks, double spaces and unicode dashes inside a
    # skill name ("machine\nlearning") must not hide the skill.
    lowered = re.sub(r"[‐‑–—]", "-", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return [
        name for name, patterns in _PATTERNS.items()
        if any(p.search(lowered) for p in patterns)
    ]


def load_jobs() -> pd.DataFrame:
    """Load jobs.csv (next to this file). Raises ValueError if unusable."""
    if not os.path.exists(JOBS_FILE):
        raise ValueError("jobs.csv was not found next to the app files.")
    try:
        df = pd.read_csv(JOBS_FILE, on_bad_lines="skip", dtype=str)
    except Exception as exc:
        raise ValueError(f"jobs.csv could not be read ({exc}).") from exc

    missing = {"title", "company", "description"} - set(df.columns)
    if missing:
        raise ValueError(f"jobs.csv is missing columns: {', '.join(sorted(missing))}.")

    # CHANGED: trim spaces, treat blank cells as missing, drop repeated rows.
    df = df.apply(lambda col: col.str.strip()).replace("", pd.NA)
    df = df.dropna(subset=["title", "description"])
    df["company"] = df["company"].fillna("Company not stated")
    keys = [c for c in ("title", "company", "url") if c in df.columns]
    df = df.drop_duplicates(subset=keys)
    if df.empty:
        raise ValueError("jobs.csv has no usable rows.")
    return df.reset_index(drop=True)


def rank_jobs(resume_text: str, target_field: str, jobs: pd.DataFrame) -> pd.DataFrame:
    """Score every job against the resume and return them best-first."""
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("The resume text is empty.")  # CHANGED
    if jobs.empty:
        raise ValueError("There are no jobs to rank.")

    df = jobs.copy()
    resume_skills = set(find_skills(resume_text))

    # Text similarity: TF-IDF vectors compared with cosine similarity.
    documents = [resume_text] + df["description"].astype(str).tolist()
    try:
        tfidf = TfidfVectorizer(stop_words="english").fit_transform(documents)
        similarity = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten() * 100
    except ValueError:  # CHANGED: "empty vocabulary" (only stop words / symbols)
        similarity = [0.0] * len(df)

    rows = []
    for i, job in df.iterrows():
        required = find_skills(job["description"])
        matched = [s for s in required if s in resume_skills]
        missing = [s for s in required if s not in resume_skills]
        role_match = title_fits_role(job["title"], target_field)

        if required:
            coverage = 100 * len(matched) / len(required)
            skill_points = 0.7 * coverage
            text_points = 0.3 * similarity[i]
            bonus = 10 if role_match else 0
            score = skill_points + text_points + bonus
            scored = True
        else:
            # CHANGED: nothing to compare, so no misleading score.
            coverage = skill_points = text_points = bonus = score = 0.0
            scored = False

        rows.append({
            "score": int(round(min(100, score))),
            "scored": scored,
            "skill_match": int(round(coverage)),
            "text_similarity": int(round(similarity[i])),
            "role_match": role_match,
            "required_count": len(required),
            "skill_points": round(skill_points, 1),
            "text_points": round(text_points, 1),
            "bonus_points": bonus,
            "matched_skills": matched,
            "missing_skills": missing,
        })

    result = pd.concat([df, pd.DataFrame(rows)], axis=1)
    # Scored jobs first (best score first), unscored jobs last.
    return result.sort_values(
        ["scored", "score"], ascending=[False, False], kind="stable"
    ).reset_index(drop=True)


def resume_quality_checks(text: str) -> list:
    """Simple, explainable checks of resume content. Returns (passed, label, advice)."""
    lowered = text.lower()
    words = len(text.split())
    sections = [s for s in ("education", "experience", "projects", "skills")
                if re.search(rf"\b{s}\b", lowered)]
    return [
        (bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)),
         "Email address",
         "Add a professional email address so recruiters can reach you."),
        (len(sections) >= 3,
         "Standard sections",
         "Use clear headings such as Education, Experience, Projects and Skills."),
        (bool(re.search(r"\d+\s?%|[$₹]\s?\d", text)),
         "Measurable results",
         "Quantify your work, e.g. 'improved accuracy by 12%'."),
        (150 <= words <= 1200,
         "Reasonable length",
         f"Your resume has {words} words; aim for roughly 300-900."),
    ]


def analyze_offline(
    resume_text: str, role: str, company: str, job_description: str = "",
    use_role_profile: bool = True,
) -> dict:
    """Keyword-based audit returning the same structure as the Gemini engine.

    The score is skill coverage: matched skills / expected skills.
    Raises ValueError if no known skills are found in the job description.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("The resume text is empty.")  # CHANGED

    if use_role_profile:
        required = ROLE_PROFILES.get(role, [])
    else:
        required = find_skills(job_description)
        if not required:
            raise ValueError(
                "No recognised skills were found in the job description. "
                "Paste the full requirements section."
            )

    resume_skills = set(find_skills(resume_text))
    matched = [s for s in required if s in resume_skills]
    missing = [s for s in required if s not in resume_skills]
    score = round(100 * len(matched) / len(required)) if required else 0

    if score >= 75:
        headline = "Strong skill coverage"
    elif score >= 50:
        headline = "Partial skill coverage"
    else:
        headline = "Significant skill gaps"

    target = f"the {role} role at {company}" if use_role_profile else "this job description"
    summary = (
        f"The resume mentions {len(matched)} of {len(required)} skills expected for "
        f"{target}. This is a keyword check: it shows which skills are written down, "
        "not how well you know them."
    )

    suggestions = []
    if missing:
        suggestions.append({
            "title": f"Cover the missing skills: {', '.join(missing[:4])}",
            "impact": "High",
            "description": (
                "If you already know these, name them in a Skills section or a project. "
                "If not, they are the best topics to learn next."
            ),
        })
    for passed, label, advice in resume_quality_checks(resume_text):
        if not passed:
            suggestions.append({"title": label, "impact": "Medium", "description": advice})

    if missing:
        roadmap = (
            f"Learn or demonstrate in this order: {', '.join(missing[:3])}. "
            "Build one small project that uses them and add it to your resume."
        )
    else:
        roadmap = "All expected skills are present. Focus on measurable results and project depth."

    return {
        "engine": "Offline",
        "match_score": score,
        "status_headline": headline,
        "summary": summary,
        "matched_skills": matched,
        "missing_skills": missing,
        "suggestions": suggestions,
        "roadmap_recommendation": roadmap,
    }
