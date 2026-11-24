# jobs_utils.py
"""Helpers for the job list: load and check jobs.csv, rank, and filter.

No Streamlit code here, so everything can be tested on its own.
The scoring itself is done by ml_matcher.rank_jobs (unchanged formula).
"""
import hashlib
from urllib.parse import urlparse

import pandas as pd

from ml_matcher import load_jobs, rank_jobs

# Optional columns of jobs.csv and the value used when a cell is empty.
OPTIONAL_COLUMNS = {
    "url": "",
    "location": "Not stated",
    "work_mode": "Not specified",
    "experience": "Not stated",
    "exp_level": "Not stated",
    "job_type": "Not stated",
    "salary": "Not listed",
    "status": "unverified",
    "last_verified": "",
    "link_type": "direct",
    "notes": "",
}
EXPERIENCE_LEVELS = ["Fresher", "0-2 years", "2+ years"]
ALL = "All"


def is_safe_url(url) -> bool:
    """Only HTTPS web links are allowed (blocks http:, javascript:, file:, etc.)."""
    parts = urlparse(str(url).strip())
    return parts.scheme == "https" and bool(parts.netloc)


def link_problem(url: str, link_type: str) -> str:
    """Return a short reason if a link breaks the link rules, else ''.

    * LinkedIn links are only allowed for rows marked link_type = search.
    * Old Workable paths (/jobs/view/CODE) are not application links; the
      correct ones look like /j/CODE/apply and must be copied from the posting.
    """
    parts = urlparse(url)
    host, path = parts.netloc.lower(), parts.path
    if "linkedin.com" in host and link_type != "search":
        return "LinkedIn link on a row that is not marked as a search link"
    if host.endswith("workable.com") and "/jobs/view/" in path:
        return "old Workable path (/jobs/view/); use /j/CODE/apply"
    return ""


def load_job_table():
    """Load jobs.csv, fill gaps and check it. Returns (DataFrame, notes).

    `notes` lists problems that were repaired, so the app can show them.
    Raises ValueError (from load_jobs) if the file is unusable.
    """
    df = load_jobs()
    notes = []

    for column, default in OPTIONAL_COLUMNS.items():
        if column not in df.columns:
            df[column] = default
        df[column] = df[column].fillna(default)

    df["status"] = df["status"].str.lower()
    df["link_type"] = df["link_type"].str.lower()

    # An unsafe or missing link is removed; a job cannot be "verified" without one.
    bad_url = ~df["url"].map(is_safe_url)
    if (bad_url & (df["url"] != "")).any():
        notes.append("Some rows had an invalid link; the link was removed.")
    df.loc[bad_url, "url"] = ""
    # Links that break the rules are not trusted: the row becomes "unverified".
    for i, row in df.iterrows():
        reason = link_problem(row["url"], row["link_type"]) if row["url"] else ""
        if reason:
            notes.append(f"'{row['title']}' ({row['company']}): {reason}. Marked unverified.")
            if row["status"] in ("verified", "unverified"):
                df.at[i, "status"] = "unverified"
    no_link_verified = (df["status"] == "verified") & (df["url"] == "")
    if no_link_verified.any():
        notes.append("Verified rows without a valid link were treated as unverified.")
        df.loc[no_link_verified, "status"] = "unverified"
    if ((df["status"] == "verified") & (df["last_verified"] == "")).any():
        notes.append("Verified rows without a last_verified date were treated as unverified.")
        df.loc[(df["status"] == "verified") & (df["last_verified"] == ""), "status"] = "unverified"

    # Stable id used by the Save button; also removes repeated postings.
    df["job_id"] = [
        hashlib.md5(f"{t}|{c}|{l}".encode()).hexdigest()[:10]
        for t, c, l in zip(df["title"], df["company"], df["location"])
    ]
    df = df.drop_duplicates(subset="job_id").reset_index(drop=True)

    df["is_demo"] = df["status"] == "demo"
    df["is_verified"] = df["status"] == "verified"
    df["is_closed"] = df["status"] == "closed"  # posting no longer available
    return df, notes


def rank_all(resume_text: str, target_role: str, jobs: pd.DataFrame):
    """Rank real and demo jobs separately. Returns (real_ranked, demo_ranked).

    Separate rankings keep the sample records from changing the TF-IDF
    weights (and so the scores) of real listings, and they can never be
    mixed into the real ranking.
    """
    # rank_jobs expects a 0, 1, 2... index, so reset it after splitting.
    real = jobs[~jobs["is_demo"]].reset_index(drop=True)
    demo = jobs[jobs["is_demo"]].reset_index(drop=True)
    real_ranked = rank_jobs(resume_text, target_role, real) if len(real) else real
    demo_ranked = rank_jobs(resume_text, target_role, demo) if len(demo) else demo
    if len(real_ranked):
        # Closed postings stay in the list (scores of the others do not change)
        # but are moved to the end. The sort is stable, so the order is otherwise kept.
        real_ranked = real_ranked.sort_values(
            "is_closed", kind="stable").reset_index(drop=True)
    return real_ranked, demo_ranked


def options_for(df: pd.DataFrame, column: str) -> list:
    """Sorted distinct values of a column, for a filter drop-down."""
    if df.empty:
        return [ALL]
    values = sorted(v for v in df[column].unique() if v and v != "Not stated")
    return [ALL] + values


def filter_jobs(df, title=ALL, location=ALL, level=ALL, job_type=ALL,
                work_mode=ALL, verified_only=False) -> pd.DataFrame:
    """Apply the filter choices. ALL means 'do not filter on this'."""
    if df.empty:
        return df
    keep = pd.Series(True, index=df.index)
    for column, choice in (("title", title), ("location", location),
                           ("exp_level", level), ("job_type", job_type),
                           ("work_mode", work_mode)):
        if choice != ALL:
            keep &= df[column] == choice
    if verified_only:
        keep &= df["is_verified"]
    return df[keep]


def short_text(text, limit=190) -> str:
    """First part of a description, cut at a word boundary."""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."
