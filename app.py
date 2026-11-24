# app.py
"""ResumeX - Resume Analyzer and Job Matcher (Streamlit front end).

This file draws the pages and keeps the session state. The scoring is done
by the backend modules:
  * ml_matcher.py  - offline skill matching, TF-IDF job ranking
  * ai_engine.py   - optional Gemini analysis
  * pdf_parser.py  - text extraction from the PDF
  * jobs_utils.py  - loading, checking and filtering jobs.csv
  * ui.py          - CSS and small HTML builders

Run with:  streamlit run app.py
"""
import io
import os
from datetime import datetime

import pandas as pd
import streamlit as st

import jobs_utils as ju
import ui
from ai_engine import AIEngineError, analyze_resume_with_gemini
from ml_matcher import ROLE_PROFILES, analyze_offline, resume_quality_checks
from pdf_parser import extract_text_from_pdf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_FILE_MB = 5
MIN_RESUME_CHARS = 50
COMPANIES = ["Google", "Amazon", "Microsoft", "Netflix", "Stripe"]
ROLES = list(ROLE_PROFILES)
IMPACT_COLORS = {"High": ui.RED, "Medium": ui.AMBER, "Low": ui.GREEN}
PAGES = {}  # filled in main(); used by the "go to page" buttons


# --- SESSION STATE -----------------------------------------------------------
# Everything the user does is kept in st.session_state, so it survives the
# reruns Streamlit does after every click and when moving between pages.
def init_state():
    state = st.session_state
    state.setdefault("resume", None)       # {"id", "name", "text", "words"}
    state.setdefault("audit", None)        # {"file_id", "results", "role", "company"}
    state.setdefault("saved", [])          # job_ids, in the order they were saved
    state.setdefault("activity", [])       # (time, text) pairs, newest first
    state.setdefault("role_pref", ROLES[0])
    state.setdefault("uploader_n", 0)      # changing it empties the file uploader


def log_activity(text: str):
    entries = st.session_state["activity"]
    entries.insert(0, (datetime.now().strftime("%H:%M"), text))
    del entries[6:]


def show(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


# --- SMALL HELPERS -----------------------------------------------------------
@st.cache_data(show_spinner=False)
def parse_resume(file_bytes: bytes) -> str:
    """Parse once per file instead of on every rerun."""
    return extract_text_from_pdf(io.BytesIO(file_bytes))


def default_api_key() -> str:
    """Key from the environment or Streamlit secrets (never from the code)."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        try:
            key = str(st.secrets.get("GEMINI_API_KEY", ""))
        except Exception:  # no secrets file: perfectly normal
            key = ""
    return key


def clear_resume():
    st.session_state["resume"] = None
    st.session_state["audit"] = None
    st.session_state["uploader_n"] += 1


def resume_uploader(key: str):
    """Upload box shared by several pages. The parsed text is kept in session state."""
    uploaded = st.file_uploader(
        "Upload your resume (PDF, up to 5 MB)", type=["pdf"],
        key=f"{key}_{st.session_state['uploader_n']}",
    )
    if uploaded is not None:
        data = uploaded.getvalue()
        file_id = f"{uploaded.name}-{len(data)}"
        current = st.session_state["resume"]
        if not (current and current["id"] == file_id):  # new file
            if len(data) > MAX_FILE_MB * 1024 * 1024:
                st.error(f"The file is larger than {MAX_FILE_MB} MB. Upload a smaller PDF.")
            else:
                try:
                    text = parse_resume(data)
                except ValueError as err:
                    st.error(str(err))
                else:
                    if len(text) < MIN_RESUME_CHARS:
                        st.warning(
                            "Little or no text was found in this PDF. It may be a scanned "
                            "image. Upload a version with selectable text."
                        )
                    else:
                        st.session_state["resume"] = {
                            "id": file_id, "name": uploaded.name,
                            "text": text, "words": len(text.split()),
                        }
                        st.session_state["audit"] = None
                        log_activity(f"Uploaded {uploaded.name}")

    resume = st.session_state["resume"]
    if resume:
        st.success(f"Resume ready: {resume['name']} ({resume['words']} words)")
        st.button("Remove resume", key=f"{key}_clear", on_click=clear_resume)
    return resume


def role_selector(key: str) -> str:
    """Target-role drop-down whose choice is remembered between pages."""
    def remember():
        st.session_state["role_pref"] = st.session_state[key]
    return st.selectbox(
        "Target role", ROLES, index=ROLES.index(st.session_state["role_pref"]),
        key=key, on_change=remember,
    )


def toggle_saved(job_id: str, title: str):
    saved = st.session_state["saved"]
    if job_id in saved:
        saved.remove(job_id)
        log_activity(f"Removed saved job: {title}")
    else:
        saved.append(job_id)
        log_activity(f"Saved job: {title}")


def clear_saved():
    st.session_state["saved"] = []


def load_jobs_or_error():
    """Return the checked job table, or None after showing an error."""
    try:
        jobs, notes = ju.load_job_table()
    except ValueError as err:
        st.error(f"The job list could not be loaded: {err}")
        return None
    for message in notes:
        st.warning(message)
    return jobs


def build_report(results: dict, role: str, company: str) -> str:
    """Plain-text report for the download button."""
    lines = [
        "RESUME ANALYSIS REPORT",
        f"Target: {role} | Benchmark: {company} | Engine: {results['engine']}",
        f"Match score: {results['match_score']}% ({results['status_headline']})",
        "Note: this is a keyword match. It shows what is written in the resume,",
        "not how well the person knows each skill.",
        "",
        results["summary"],
        "",
        "Matched skills: " + (", ".join(results["matched_skills"]) or "none"),
        "Skill gaps: " + (", ".join(results["missing_skills"]) or "none"),
        "",
        "Suggestions:",
    ]
    for s in results["suggestions"]:
        lines.append(f"- [{s['impact']}] {s['title']}: {s['description']}")
    lines += ["", "Roadmap: " + results["roadmap_recommendation"]]
    return "\n".join(lines)


# --- JOB CARD ----------------------------------------------------------------
def job_card(row, prefix: str):
    """One job card. `row` comes from ml_matcher.rank_jobs, so the match
    numbers shown here are exactly the ones the ML matcher produced."""
    with st.container(border=True):
        show(ui.one_line(
            ui.job_head(row) + ui.job_match(row)
            + ui.job_skills_and_text(row, ju.short_text(row["description"]))
        ))
        link_col, save_col = st.columns([3, 2])
        with link_col:
            url = row["url"]
            if not url:
                st.caption("No application link available.")
            elif row["link_type"] == "search":
                st.link_button("Search on LinkedIn (search page, not a vacancy)", url)
            elif row["is_verified"]:
                st.link_button("Apply Now", url, type="primary")
            else:
                st.link_button("Open posting (not verified)", url)
        with save_col:
            saved = row["job_id"] in st.session_state["saved"]
            st.button(
                "Saved - remove" if saved else "Save job",
                key=f"{prefix}_{row['job_id']}",
                on_click=toggle_saved, args=(row["job_id"], row["title"]),
            )


def job_grid(df, prefix: str):
    """Show job cards in two columns (they stack on small screens)."""
    rows = [row for _, row in df.iterrows()]
    for start in range(0, len(rows), 2):
        columns = st.columns(2, gap="medium")
        for column, row in zip(columns, rows[start:start + 2]):
            with column:
                job_card(row, prefix)


# --- PAGE: DASHBOARD -----------------------------------------------------------
def dashboard_page():
    show(ui.page_header(
        "Welcome to ResumeX",
        "Check your resume against a role and find jobs that match your skills.",
    ))
    show(ui.note(
        "ResumeX reads your PDF resume and compares the skills it mentions with a target "
        "role or with real job listings. It measures what is written in your resume, "
        "not how well you know each skill."
    ))

    jobs = load_jobs_or_error()
    audit = st.session_state["audit"]
    cards = []
    if jobs is not None:
        real = jobs[~jobs["is_demo"]]
        checked = sorted(d for d in real["last_verified"] if d)
        cards.append((
            "briefcase", str(len(real)), "Real job listings",
            f"{int(real['is_verified'].sum())} verified"
            + (f", last checked {checked[-1]}" if checked else ""),
        ))
    cards.append(("bookmark", str(len(st.session_state["saved"])), "Saved jobs",
                  "Kept for this browser session"))
    if audit:
        cards.append(("activity", f"{audit['results']['match_score']}%", "Latest analysis",
                      f"{audit['role']} - {audit['results']['engine']} engine"))
    else:
        cards.append(("activity", "Not run yet", "Latest analysis",
                      "Run a resume analysis to see it here"))
    show(ui.stat_cards(cards))

    left, middle, right = st.columns(3, gap="medium")
    with left, st.container(border=True):
        show(f'<div class="icon-box">{ui.icon("upload")}</div>'
             '<div class="card-title">1. Upload your resume</div>')
        resume_uploader("up_dashboard")
    with middle, st.container(border=True):
        show(f'<div class="icon-box">{ui.icon("file")}</div>'
             '<div class="card-title">2. Analyse your resume</div>'
             '<p class="sub">See matched and missing skills, quality checks and advice.</p>')
        if st.button("Open Resume Analysis"):
            st.switch_page(PAGES["analysis"])
    with right, st.container(border=True):
        show(f'<div class="icon-box">{ui.icon("briefcase")}</div>'
             '<div class="card-title">3. Find matching jobs</div>'
             '<p class="sub">Real listings ranked by the ML matcher, with Apply links.</p>')
        if st.button("Open Job Recommendations"):
            st.switch_page(PAGES["jobs"])

    st.markdown("### Recent activity")
    with st.container(border=True):
        if st.session_state["activity"]:
            show("".join(
                f'<div class="activity"><time>{ui.e(t)}</time><span>{ui.e(text)}</span></div>'
                for t, text in st.session_state["activity"]
            ))
        else:
            st.caption("Uploads, analyses and saved jobs from this session will appear here.")


# --- PAGE: RESUME ANALYSIS -----------------------------------------------------
def run_analysis(resume_text, role, company, job_description, use_profile, api_key):
    """Gemini first (if a key was given), offline analysis as the fallback."""
    results = None
    if api_key.strip():
        try:
            results = analyze_resume_with_gemini(
                api_key, resume_text, role, company, job_description)
        except AIEngineError as err:
            st.warning(f"{err} Showing the offline analysis instead.")
    if results is None:
        try:
            results = analyze_offline(
                resume_text, role, company, job_description, use_profile)
        except ValueError as err:
            st.error(str(err))
    return results


def render_audit(results: dict, resume_text: str, role: str, company: str):
    show(ui.score_ring(
        results["match_score"], results["status_headline"], results["summary"]))
    st.caption(
        f"Analysis engine: {results['engine']}. Keyword matching measures what is "
        "mentioned in your resume, not your actual proficiency."
    )
    for message in results.get("notes", []):
        show(ui.note(message, warn=True))

    found, gaps = results["matched_skills"], results["missing_skills"]
    total = len(found) + len(gaps)
    coverage = round(100 * len(found) / total) if total else 0
    st.markdown("### Skills")
    show(ui.one_line(
        '<div class="card">'
        + ui.progress("Skills found in your resume", f"{len(found)} of {total}", coverage)
        + '<div class="label">Matched skills</div>' + ui.chips(found, "ok")
        + '<div class="label">Missing or not mentioned</div>' + ui.chips(gaps, "miss")
        + "</div>"
    ))

    st.markdown("### Resume quality checks")
    show('<div class="card">' + "".join(
        ui.quality_row(passed, label, advice)
        for passed, label, advice in resume_quality_checks(resume_text)
    ) + "</div>")

    st.markdown("### AI recommendations")
    if not results["suggestions"]:
        st.success("No major issues found.")
    for s in results["suggestions"]:
        show(ui.tip(s["title"], s["impact"], s["description"],
                    IMPACT_COLORS.get(s["impact"], ui.AMBER)))

    st.markdown("### Suggested learning roadmap")
    show(ui.note(results["roadmap_recommendation"] or "No roadmap was generated."))

    st.download_button(
        "Download report (.txt)", build_report(results, role, company),
        file_name="resume_report.txt",
    )


def analysis_page():
    show(ui.page_header(
        "Resume Analysis", "Compare your resume with a role or a job description."))
    left, right = st.columns([2, 3], gap="large")

    with left, st.container(border=True):
        resume = resume_uploader("up_analysis")
        role = role_selector("role_analysis")
        source = st.radio(
            "Compare my resume with",
            ["A top tech company's expectations", "A job description I paste"],
        )
        use_profile = source.startswith("A top")
        if use_profile:
            company = st.selectbox("Company", COMPANIES)
            job_description = (
                f"Typical expectations for a {role} at {company}. "
                f"Core skills: {', '.join(ROLE_PROFILES[role])}. "
                "Strong data structures, algorithms and clean coding practices."
            )
        else:
            company = "Pasted job description"
            job_description = st.text_area(
                "Job description", height=150,
                placeholder="Paste the requirements section of the job posting here...",
            )
        with st.expander("Optional: use Gemini AI"):
            api_key = st.text_input(
                "Gemini API key", type="password", value=default_api_key(),
                help="Leave empty to use the offline keyword analysis.",
            )
            st.caption("Without a key, or if Gemini fails, the offline analysis is used.")
        run = st.button("Run resume analysis", type="primary")

        if run:
            st.session_state["audit"] = None
            if not resume:
                st.error("Upload a readable PDF resume first.")
            elif not use_profile and len(job_description.strip()) < 30:
                st.warning("Paste a longer job description (at least a couple of sentences).")
            else:
                with st.spinner("Analysing your resume..."):
                    results = run_analysis(resume["text"], role, company,
                                           job_description, use_profile, api_key)
                if results:
                    st.session_state["audit"] = {
                        "file_id": resume["id"], "results": results,
                        "role": role, "company": company,
                    }
                    log_activity(f"Analysed resume for {role} ({results['engine']} engine)")

    with right:
        audit = st.session_state["audit"]
        if audit and resume and audit["file_id"] == resume["id"]:
            render_audit(audit["results"], resume["text"], audit["role"], audit["company"])
        else:
            show(ui.note("Your results will appear here after you upload a resume and "
                         "press Run resume analysis."))


# --- PAGE: JOB RECOMMENDATIONS ---------------------------------------------------
def jobs_page():
    show(ui.page_header(
        "Job Recommendations",
        "Listings ranked by how many of their skills your resume mentions.",
    ))
    resume = st.session_state["resume"]
    if not resume:
        with st.container(border=True):
            st.markdown("**Upload your resume to see your match percentages.**")
            resume = resume_uploader("up_jobs")
        if not resume:
            return

    jobs = load_jobs_or_error()
    if jobs is None:
        return

    top_left, top_right = st.columns([1, 2], gap="large")
    with top_left:
        role = role_selector("role_jobs")
    with top_right:
        with st.expander("How is the match calculated?"):
            st.markdown(
                "- **70%** skill coverage: how many of the skills named in the job "
                "description appear in your resume.\n"
                "- **30%** text similarity: TF-IDF cosine similarity between your resume and "
                "the job description.\n"
                "- **+10** if the job title fits your target role.\n\n"
                "The result is capped at 100. It shows how much of the job description your "
                "resume mentions. It is **not** the chance of getting the job or a measure of "
                "how well you know the skills. Jobs with no recognised skills are not rated."
            )

    real_only = st.toggle("Real listings only", value=True,
                          help="Hide the sample (demo) records.")
    pool = jobs[~jobs["is_demo"]] if real_only else jobs
    f1, f2, f3, f4 = st.columns(4)
    title = f1.selectbox("Job role", ju.options_for(pool, "title"))
    location = f2.selectbox("Location", ju.options_for(pool, "location"))
    level = f3.selectbox("Experience level", [ju.ALL] + ju.EXPERIENCE_LEVELS)
    job_type = f4.selectbox("Job type", ju.options_for(pool, "job_type"))
    f5, f6 = st.columns([1, 3])
    work_mode = f5.selectbox("Work mode", ju.options_for(pool, "work_mode"))
    verified_only = f6.toggle("Verified listings only", value=False)

    # Rank first, filter afterwards: filters never change a job's score.
    real_ranked, demo_ranked = ju.rank_all(resume["text"], role, jobs)
    choices = dict(title=title, location=location, level=level, job_type=job_type,
                   work_mode=work_mode, verified_only=verified_only)
    real_shown = ju.filter_jobs(real_ranked, **choices)

    st.markdown(f"### Real listings ({len(real_shown)} of {len(real_ranked)})")
    if len(real_shown):
        job_grid(real_shown, "real")
    else:
        st.info("No real listings match these filters. Try 'All' in one of them.")

    if not real_only:
        demo_shown = ju.filter_jobs(demo_ranked, **choices)
        st.markdown(f"### Sample listings - demo ({len(demo_shown)})")
        show(ui.note(
            "These are sample records for practice. They are not real vacancies and "
            "their links are search pages.", warn=True))
        if len(demo_shown):
            job_grid(demo_shown, "demo")
        else:
            st.caption("No sample listings match these filters.")


# --- PAGE: SAVED JOBS ------------------------------------------------------------
def saved_page():
    show(ui.page_header("Saved Jobs", "Jobs you bookmarked in this session."))
    saved_ids = st.session_state["saved"]
    if not saved_ids:
        show(ui.note("No saved jobs yet. Use 'Save job' on a job card in Job Recommendations."))
        return

    jobs = load_jobs_or_error()
    if jobs is None:
        return
    resume = st.session_state["resume"]
    if resume:  # show the match for saved jobs too
        real_ranked, demo_ranked = ju.rank_all(
            resume["text"], st.session_state["role_pref"], jobs)
        table = pd.concat([t for t in (real_ranked, demo_ranked) if len(t)],
                          ignore_index=True)
    else:
        table = jobs
    table = table[table["job_id"].isin(saved_ids)]
    if len(table) < len(saved_ids):
        st.warning("Some saved jobs are no longer in jobs.csv.")

    st.caption("Saved jobs are kept only for this browser session. "
               "They are cleared when you refresh or close the tab.")
    st.button("Clear all saved jobs", on_click=clear_saved)
    if not resume:
        show(ui.note("Upload a resume to see your match for these jobs."))
    job_grid(table, "saved")


# --- PAGE: ABOUT -----------------------------------------------------------------
def about_page():
    show(ui.page_header("About ResumeX", "How the application works."))
    st.markdown("### What it does")
    st.write(
        "ResumeX reads a PDF resume, finds the technical skills written in it, and "
        "compares them with a target role or with job listings. It also checks the "
        "resume for common problems such as a missing email address."
    )
    st.markdown("### How the job match is calculated")
    st.write(
        "Score = 70% skill coverage + 30% TF-IDF text similarity, plus 10 if the job "
        "title fits the target role (maximum 100). Skills are found by whole-word "
        "keyword matching against a fixed skill list. The score describes how much of "
        "a job description your resume mentions. It is not the probability of being "
        "hired and does not measure how well you know a skill."
    )
    st.markdown("### About the job data")
    st.write(
        "jobs.csv contains listings whose pages were opened on the date shown on each "
        "card (status 'verified'). Companies can close a vacancy at any time, so check "
        "the page before applying. Sample (demo) records are practice data, shown only "
        "when 'Real listings only' is switched off."
    )
    st.markdown("### Gemini and offline mode")
    st.write(
        "Gemini is optional. Without an API key, or if Gemini fails, ResumeX uses its "
        "offline keyword analysis. If you use Gemini, the resume text is sent to Google "
        "to produce the analysis."
    )
    st.markdown("### Technology")
    st.write("Python, Streamlit, pandas, scikit-learn (TF-IDF, cosine similarity), "
             "pdfplumber and the Google Gemini API (optional).")


# --- MAIN ------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="ResumeX", page_icon="📄", layout="wide")
    st.markdown(ui.CSS, unsafe_allow_html=True)
    try:
        st.logo(os.path.join(BASE_DIR, "assets", "logo.svg"))
    except Exception:  # a missing logo must never stop the app
        pass
    init_state()

    PAGES["dashboard"] = st.Page(dashboard_page, title="Dashboard",
                                 icon=":material/dashboard:", default=True)
    PAGES["analysis"] = st.Page(analysis_page, title="Resume Analysis",
                                icon=":material/description:")
    PAGES["jobs"] = st.Page(jobs_page, title="Job Recommendations",
                            icon=":material/work:")
    PAGES["saved"] = st.Page(saved_page, title="Saved Jobs",
                             icon=":material/bookmark:")
    PAGES["about"] = st.Page(about_page, title="About ResumeX",
                             icon=":material/info:")
    navigation = st.navigation(list(PAGES.values()))
    st.sidebar.caption(
        "Your resume is used only in this session. It is sent to Google only "
        "if you add a Gemini API key."
    )
    navigation.run()


if __name__ == "__main__":
    main()
