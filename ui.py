# ui.py
"""Look and feel of ResumeX: one CSS block plus small HTML builders.

Nothing here calculates a score. It only turns values into HTML.
"""
import html

# Status colors tuned to pop cleanly on dark black/purple surfaces.
GREEN, AMBER, RED = "#22c55e", "#f59e0b", "#fb7185"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, .stApp {
    font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
    color: #f5f3ff;
}

.stApp {
    background: radial-gradient(circle at top right, rgba(124, 58, 237, 0.16), transparent 45%), #0c0b12;
}

#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 1280px; padding: 4rem 2.2rem 3rem 2.2rem; }

/* Sidebar & Navigation - high contrast on black/purple */
[data-testid="stSidebar"] {
    background: #13111c;
    border-right: 1px solid rgba(168, 85, 247, 0.25);
}
[data-testid="stSidebar"] * {
    color: #e9d5ff;
}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"],
[data-testid="stSidebar"] a {
    color: #e2dcf5 !important;
    border-radius: 10px;
    padding: 6px 10px;
}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover,
[data-testid="stSidebar"] a:hover {
    background: rgba(139, 92, 246, 0.22) !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
    background: linear-gradient(90deg, rgba(124, 58, 237, 0.35), rgba(168, 85, 247, 0.2)) !important;
    color: #ffffff !important;
    border-left: 3px solid #a855f7;
}

/* General Streamlit labels & text visibility */
label, .stMarkdown p, .stCaption, [data-testid="stWidgetLabel"] p {
    color: #e9e5f5;
}

/* page header */
.page-head { margin-bottom: 18px; }
.page-head h1 { font-size: 28px; font-weight: 700; color: #ffffff; margin: 0; padding: 0; }
.page-head p { color: #b8b0d3; font-size: 15px; margin: 4px 0 0 0; }
h3 { color: #f3e8ff; font-weight: 650; }

/* cards */
.card, [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px;
    transition: box-shadow .2s ease, transform .2s ease, border-color .2s ease;
}
.card {
    background: #161322;
    border: 1px solid rgba(168, 85, 247, 0.24);
    padding: 20px 22px;
    margin: 6px 0 16px 0;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
}
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #161322;
    border-color: rgba(168, 85, 247, 0.22);
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: rgba(192, 132, 252, 0.55);
    box-shadow: 0 8px 24px rgba(124, 58, 237, 0.22);
}
.card-title { font-size: 16px; font-weight: 650; color: #ffffff; margin: 0 0 4px 0; }
.sub { color: #b8b0d3; font-size: 14px; line-height: 1.55; margin: 2px 0 0 0; }
.label {
    font-size: 11px; font-weight: 600; color: #c4b5fd; text-transform: uppercase;
    letter-spacing: .06em; margin: 12px 0 6px 0;
}
.icon-box {
    width: 38px; height: 38px; border-radius: 10px;
    background: rgba(139, 92, 246, 0.2); color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.35);
    display: flex; align-items: center; justify-content: center; margin-bottom: 10px;
}
.ic { width: 18px; height: 18px; vertical-align: -3px; }

/* overview stat cards */
.stats {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px; margin: 8px 0 20px 0;
}
.stat {
    background: #161322; border: 1px solid rgba(168, 85, 247, 0.24);
    border-radius: 16px; padding: 16px 18px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}
.stat .num { font-size: 26px; font-weight: 700; color: #ffffff; line-height: 1.2; }
.stat .name { font-size: 13px; color: #d8b4fe; margin-top: 2px; }
.stat .hint { font-size: 12px; color: #9ca3af; margin-top: 6px; }

/* notices */
.note {
    background: rgba(124, 58, 237, 0.16); border: 1px solid rgba(168, 85, 247, 0.4);
    color: #f3e8ff; border-radius: 12px; padding: 10px 14px;
    font-size: 13px; line-height: 1.5; margin: 8px 0 14px 0;
}
.note.warn {
    background: rgba(245, 158, 11, 0.14); border-color: rgba(245, 158, 11, 0.45);
    color: #fde68a;
}

/* score ring */
.result-top { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }
@property --p { syntax: '<number>'; inherits: false; initial-value: 0; }
.ring {
    --p: 0; flex: none; width: 108px; height: 108px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: conic-gradient(var(--c) calc(var(--p) * 1%), rgba(168, 85, 247, 0.22) 0);
    animation: fill 1.1s ease-out;
}
@keyframes fill { from { --p: 0; } }
.ring-inner {
    width: 86px; height: 86px; border-radius: 50%;
    background: #161322; color: #ffffff;
    display: flex; align-items: center; justify-content: center;
    font-size: 26px; font-weight: 700;
}
.headline { margin: 0; font-size: 20px; font-weight: 650; color: #ffffff; }

/* progress bar */
.bar { height: 8px; background: rgba(168, 85, 247, 0.2); border-radius: 6px; overflow: hidden; }
.bar > span {
    display: block; height: 100%; border-radius: 6px;
    background: linear-gradient(90deg, #7c3aed, #c084fc); animation: grow .9s ease-out;
}
@keyframes grow { from { width: 0; } }
.bar-head {
    display: flex; justify-content: space-between; font-size: 13px;
    color: #e9d5ff; font-weight: 500; margin-bottom: 6px;
}

/* chips and badges */
.chip {
    display: inline-block; margin: 0 5px 5px 0; padding: 2px 10px;
    border-radius: 10px; font-size: 12px; font-weight: 500;
}
.chip.ok {
    background: rgba(34, 197, 94, 0.16); color: #86efac;
    border: 1px solid rgba(34, 197, 94, 0.35);
}
.chip.miss {
    background: rgba(251, 113, 133, 0.16); color: #fda4af;
    border: 1px solid rgba(251, 113, 133, 0.35);
}
.none { color: #9ca3af; font-size: 12px; }
.tag {
    display: inline-block; font-size: 11px; font-weight: 600;
    padding: 2px 9px; border-radius: 9px; white-space: nowrap;
}
.tag.live {
    background: rgba(34, 197, 94, 0.16); color: #86efac;
    border: 1px solid rgba(34, 197, 94, 0.35);
}
.tag.demo {
    background: rgba(245, 158, 11, 0.16); color: #fcd34d;
    border: 1px solid rgba(245, 158, 11, 0.35);
}
.tag.unv {
    background: rgba(168, 85, 247, 0.18); color: #e9d5ff;
    border: 1px solid rgba(168, 85, 247, 0.4);
}

/* recommendations and quality checks */
.tip {
    background: #1a1629; border: 1px solid rgba(168, 85, 247, 0.25);
    border-left: 4px solid var(--c); border-radius: 12px;
    padding: 12px 16px; margin-bottom: 10px;
}
.tip-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.tip-title { color: #ffffff; font-weight: 600; font-size: 14px; }
.tip p { margin: 5px 0 0 0; color: #c4bddb; font-size: 13px; line-height: 1.5; }
.badge {
    background: #13111c; border: 1px solid var(--c); color: var(--c);
    border-radius: 9px; padding: 1px 8px; font-size: 11px; white-space: nowrap;
}
.check {
    display: flex; gap: 10px; align-items: flex-start; padding: 8px 0;
    border-bottom: 1px solid rgba(168, 85, 247, 0.16); font-size: 14px;
}
.check:last-child { border-bottom: 0; }
.check .sub { margin: 0; font-size: 13px; }

/* job card pieces */
.job-top { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.job-title { font-size: 16px; font-weight: 650; color: #ffffff; line-height: 1.3; }
.job-co { font-size: 13px; color: #c4b5fd; margin-top: 2px; }
.meta {
    display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 10px 0;
    font-size: 13px; color: #cfc9e6;
}
.meta span { display: inline-flex; align-items: center; gap: 5px; }
.explain { font-size: 12px; color: #a8a0c4; margin: 6px 0 0 0; }
.job-desc { font-size: 13px; color: #d6d1e8; line-height: 1.5; margin: 10px 0 0 0; }
.verified-on { font-size: 12px; color: #a8a0c4; margin-top: 8px; }
.activity {
    display: flex; gap: 10px; padding: 8px 0;
    border-bottom: 1px solid rgba(168, 85, 247, 0.16); font-size: 14px;
}
.activity:last-child { border-bottom: 0; }
.activity time { color: #a8a0c4; font-size: 12px; min-width: 52px; }

/* Streamlit buttons - clearly visible purple & dark purple-slate */
.stButton > button, .stDownloadButton > button, .stLinkButton > a {
    background: #241d38 !important;
    color: #ffffff !important;
    border: 1px solid rgba(192, 132, 252, 0.5) !important;
    border-radius: 10px;
    font-weight: 500;
    transition: transform .15s ease, background .15s ease, border-color .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
    background: #332752 !important;
    border-color: #d8b4fe !important;
    color: #ffffff !important;
    transform: translateY(-1px);
}
.stButton > button[kind="primary"], .stLinkButton > a[kind="primary"] {
    background: linear-gradient(90deg, #7c3aed, #9333ea) !important;
    border: 1px solid #c084fc !important;
    color: #ffffff !important;
}
.stButton > button[kind="primary"]:hover, .stLinkButton > a[kind="primary"]:hover {
    background: linear-gradient(90deg, #8b5cf6, #a855f7) !important;
    color: #ffffff !important;
}

/* File uploader dropzone */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed rgba(192, 132, 252, 0.55) !important;
    border-radius: 14px;
    background: #161322 !important;
    color: #f5f3ff !important;
}
[data-testid="stFileUploaderDropzone"] * {
    color: #e9d5ff !important;
}

@media (max-width: 760px) {
    .block-container { padding: 1.2rem 1rem 2rem 1rem; }
    .page-head h1 { font-size: 23px; }
    .ring { width: 92px; height: 92px; } .ring-inner { width: 72px; height: 72px; font-size: 22px; }
}
@media (prefers-reduced-motion: reduce) {
    .ring, .bar > span { animation: none; }
    .card, .stButton > button, .stDownloadButton > button, .stLinkButton > a,
    [data-testid="stVerticalBlockBorderWrapper"] { transition: none; }
}
</style>
"""

# Small line icons (24x24 paths, drawn with currentColor).
ICONS = {
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "file": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5Z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h8"/>',
    "briefcase": '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    "bookmark": '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2Z"/>',
    "pin": '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "cash": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>',
    "grad": '<path d="m22 10-10-5-10 5 10 5Z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "cross": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "spark": '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z"/>',
}


def e(value) -> str:
    """Escape text before placing it inside HTML."""
    return html.escape(str(value))


def one_line(markup: str) -> str:
    """Join lines so Markdown never treats indented HTML as a code block."""
    return " ".join(line.strip() for line in markup.splitlines())


def icon(name: str) -> str:
    return (
        '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'
    )


def score_color(score: int) -> str:
    return GREEN if score >= 75 else AMBER if score >= 50 else RED


def page_header(title: str, subtitle: str) -> str:
    return f'<div class="page-head"><h1>{e(title)}</h1><p>{e(subtitle)}</p></div>'


def stat_cards(items) -> str:
    """items: (icon_name, number_text, name, hint) tuples."""
    cards = "".join(
        f'<div class="stat"><div class="icon-box">{icon(i)}</div><div class="num">{e(n)}</div>'
        f'<div class="name">{e(name)}</div><div class="hint">{e(hint)}</div></div>'
        for i, n, name, hint in items
    )
    return f'<div class="stats">{cards}</div>'


def chips(items, kind: str) -> str:
    """kind is 'ok' (green) or 'miss' (red)."""
    if not items:
        return '<span class="none">None</span>'
    return "".join(f'<span class="chip {kind}">{e(i)}</span>' for i in items)


def progress(label: str, value_text: str, percent: int) -> str:
    percent = max(0, min(100, int(percent)))
    return (
        f'<div class="bar-head"><span>{e(label)}</span><b>{e(value_text)}</b></div>'
        f'<div class="bar"><span style="width:{percent}%"></span></div>'
    )


def score_ring(score: int, headline: str, summary: str) -> str:
    return one_line(f"""
    <div class="card"><div class="result-top">
      <div class="ring" style="--p:{score}; --c:{score_color(score)}">
        <div class="ring-inner">{score}%</div></div>
      <div style="flex:1 1 280px">
        <p class="headline">{e(headline)}</p><p class="sub">{e(summary)}</p>
      </div></div></div>
    """)


def tip(title: str, impact: str, description: str, color: str) -> str:
    return one_line(f"""
    <div class="tip" style="--c:{color}">
      <div class="tip-head"><span class="tip-title">{e(title)}</span>
        <span class="badge">{e(impact)} impact</span></div>
      <p>{e(description)}</p></div>
    """)


def quality_row(passed: bool, label: str, advice: str) -> str:
    mark = (f'<span style="color:{GREEN}">{icon("check")}</span>' if passed
            else f'<span style="color:{AMBER}">{icon("cross")}</span>')
    text = "Looks good." if passed else advice
    return (f'<div class="check">{mark}<div><b>{e(label)}</b>'
            f'<p class="sub">{e(text)}</p></div></div>')


def note(text: str, warn: bool = False) -> str:
    return f'<div class="note{" warn" if warn else ""}">{e(text)}</div>'


def status_tag(row) -> str:
    if row["is_demo"]:
        return '<span class="tag demo">Sample (demo)</span>'
    if row["is_verified"]:
        return '<span class="tag live">&#10003; Verified listing</span>'
    return '<span class="tag unv">Not verified</span>'


def job_head(row) -> str:
    return one_line(f"""
    <div class="job-top"><div><div class="job-title">{e(row['title'])}</div>
      <div class="job-co">{e(row['company'])}</div></div>{status_tag(row)}</div>
    <div class="meta">
      <span>{icon('pin')}{e(row['location'])}</span>
      <span>{icon('monitor')}{e(row['work_mode'])}</span>
      <span>{icon('clock')}{e(row['job_type'])}</span>
      <span>{icon('grad')}{e(row['experience'])}</span>
      <span>{icon('cash')}{e(row['salary'])}</span>
    </div>
    """)


def job_match(row) -> str:
    """The match block. Every number comes from ml_matcher.rank_jobs."""
    if "score" not in row or not row["scored"]:
        return ('<p class="explain">Not rated: no recognised skills in this description, '
                'so a match percentage would be misleading.</p>')
    score = int(row["score"])
    head = (f'<div class="bar-head"><span>Resume match</span>'
            f'<b style="color:{score_color(score)}">{score}%</b></div>'
            f'<div class="bar"><span style="width:{score}%"></span></div>')
    why = (f"{int(row['skill_match'])}% of {int(row['required_count'])} recognised skills found, "
           f"{int(row['text_similarity'])}% text similarity. "
           f"Points: skills {row['skill_points']} + text {row['text_points']} "
           f"+ role fit {row['bonus_points']} = {score}")
    return head + f'<p class="explain">{e(why)}</p>'


def job_skills_and_text(row, description: str) -> str:
    if "matched_skills" not in row:
        return f'<p class="job-desc">{e(description)}</p>'
    verified = ""
    if row["is_verified"] and row["last_verified"]:
        verified = f'<div class="verified-on">Last verified: {e(row["last_verified"])}</div>'
    return one_line(f"""
    <div class="label">Matched skills</div>{chips(row['matched_skills'], 'ok')}
    <div class="label">Missing skills</div>{chips(row['missing_skills'], 'miss')}
    <p class="job-desc">{e(description)}</p>{verified}
    """)
