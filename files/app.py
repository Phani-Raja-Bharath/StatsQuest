import hmac
import json
import os
import random
import re
import html
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from content_loader import get_content, load_content, missing_required_keys, split_markdown_title
import db  # module reference (not `from db import USE_POSTGRES`) so it reflects
           # the value *after* configure_database() runs, not the import-time default
from db import (
    add_attempt,
    all_participants,
    configure_database,
    conn,
    delete_participant,
    ensure_schema,
    find_participant_pid_by_name,
    leaderboard,
    level_score,
    make_pid,
    participant_exists,
    participant_stats,
    register_participant,
    reset_participant_attempts,
    sql,
    total_xp,
)
import navigation
from navigation import PAGE_LEVELS, PAGE_OPTIONS
from level_pages.level_1 import render as render_level_1
from level_pages.level_2 import render as render_level_2
from level_pages.level_3 import render as render_level_3
from level_pages.level_4 import render as render_level_4
from level_pages.level_5 import render as render_level_5
from scoring import (
    BADGE_DESCRIPTIONS,
    CHALLENGE_META,
    CHALLENGE_POINTS,
    CONSOLATION_FRACTION,
    LEVEL_CHALLENGES,
    LEVEL_REQUIRED_CHALLENGES,
    LEVELS,
    MAX_WRONG_ATTEMPTS,
    PERFECT_SCORE,
    badge_for_xp,
    boss_defeated_percent,
    challenge_label,
    challenge_labels,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "stats_game.db")
CONTENT_FILE = os.path.join(APP_DIR, "content.json")

CONTENT = load_content(CONTENT_FILE)
CONTENT_ISSUES = missing_required_keys(CONTENT)

def content_get(path: str, default: Any = "") -> Any:
    return get_content(CONTENT, path, default)

_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

def csv_safe_export(df, columns):
    """Return a copy of df with the given columns neutralized against CSV/
    spreadsheet formula injection (a cell like "=cmd|'/c calc'!A1" executing
    when the exported file is later opened in Excel/Sheets). Student-supplied
    text (names, free-text answers) flows into these exports untouched
    otherwise, so a leading =/+/-/@/tab/CR gets a defusing leading quote.
    Only affects the downloaded file -- the on-screen table is unchanged."""
    safe = df.copy()
    for column in columns:
        if column not in safe:
            continue
        safe[column] = safe[column].map(
            lambda value: f"'{value}" if str(value).startswith(_CSV_FORMULA_TRIGGERS) else value
        )
    return safe

def get_secret(name):
    value = os.environ.get(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:
        return None

DATABASE_URL = get_secret("DATABASE_URL") or get_secret("NEON_DATABASE_URL")
ADMIN_PASSWORD = get_secret("STATSQUEST_ADMIN_PASSWORD")
# No hardcoded fallback password: if the secret isn't set, admin access is
# disabled outright rather than falling back to a guessable default that
# would otherwise be sitting in this public source file.
ADMIN_ACCESS_ENABLED = bool(ADMIN_PASSWORD)
configure_database(DB, DATABASE_URL)

def show_database_error(detail: str = "") -> None:
    """A clear, actionable message instead of a raw crash when a database
    operation fails -- most commonly because a deployment is silently
    running on local file storage (no DATABASE_URL secret configured) on a
    host whose filesystem doesn't support that, e.g. Streamlit Community
    Cloud mounting the app read-only from its git checkout."""
    st.error(
        "⚠️ **This app can't reach its database right now.**\n\n"
        "If you're a student: this isn't something you did wrong — please tell your instructor.\n\n"
        "If you're the instructor: this deployment is most likely missing its `DATABASE_URL` "
        "secret (Neon Postgres). Local file storage does not persist reliably on most hosting "
        "platforms, including Streamlit Community Cloud. Add `DATABASE_URL` under this app's "
        "**Settings → Secrets**, then reload."
    )
    if detail:
        with st.expander("Technical details"):
            st.code(detail)
    st.stop()

st.set_page_config(
    page_title="StatsQuest: Modeling & Simulation",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown("""
<style>
:root {
    --statsquest-card-border: rgba(120,120,120,.25);
    --statsquest-accent: #2563eb;
    --statsquest-accent-hover: #1d4ed8;
}

.block-container {
    max-width: 1180px;
    padding: 2rem 1.5rem 3rem;
}

.game-title {
    font-size: clamp(1.65rem, 6vw, 2.1rem);
    line-height: 1.25;
    font-weight: 800;
    margin: 0 0 .2rem;
    padding-top: .1rem;
}

.game-subtitle {
    color: rgba(128,128,128,.95);
    margin-bottom: 1.15rem;
    font-size: clamp(.95rem, 3vw, 1rem);
}

.mobile-topbar {
    display: none;
    color: #111827;
}

.level-card {
    border: 1px solid var(--statsquest-card-border);
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 10px;
}

div[data-testid="stRadio"] {
    border: 1px solid rgba(37, 99, 235, .22);
    border-left: 6px solid #2563eb;
    border-radius: 8px;
    padding: 14px 16px 12px;
    margin: 12px 0 10px;
    background: #f8fafc;
}

div[data-testid="stRadio"] > label {
    font-weight: 700;
}

.challenge-status {
    border: 1.5px solid;
    border-left-width: 6px;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 8px 0 14px;
}

.challenge-status-title {
    font-weight: 700;
    margin-bottom: 4px;
}

.challenge-status-correct {
    border-color: #16a34a;
    background: #f0fdf4;
    color: #14532d;
}

.challenge-status-one-wrong {
    border-color: #d97706;
    background: #fffbeb;
    color: #78350f;
}

.challenge-status-two-wrong {
    border-color: #dc2626;
    background: #fef2f2;
    color: #7f1d1d;
}

.challenge-status-info {
    border-color: #2563eb;
    background: #eff6ff;
    color: #1e3a8a;
}

.challenge-status-unanswered {
    border-color: #2563eb;
    background: #eff6ff;
    color: #1e3a8a;
}

.big-score {
    font-size: clamp(1.5rem, 5vw, 2rem);
    font-weight: 800;
}

.small-muted {color:#777; font-size:.9rem;}

div[data-testid="stMetric"] {
    border: 1px solid var(--statsquest-card-border);
    border-radius: 8px;
    padding: .65rem .75rem;
}

div[data-testid="stMetricValue"] {
    font-size: clamp(1.2rem, 5vw, 1.85rem);
    line-height: 1.1;
}

div[data-testid="stDataFrame"] {
    overflow-x: auto;
}

div[data-testid="stAlert"] {
    border-radius: 8px;
}

div[data-testid="stTextInput"] input {
    min-height: 2.75rem;
}

div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stDownloadButton"] > button[kind="primary"] {
    background: var(--statsquest-accent);
    border-color: var(--statsquest-accent);
    color: #fff;
}

div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stDownloadButton"] > button[kind="primary"]:hover {
    background: var(--statsquest-accent-hover);
    border-color: var(--statsquest-accent-hover);
    color: #fff;
}

@media (max-width: 700px) {
    .block-container {
        padding: .75rem .75rem 2rem;
        max-width: 100%;
    }

    .game-title {
        font-size: clamp(1.35rem, 7vw, 1.65rem);
        margin-bottom: .35rem;
    }

    .game-subtitle {
        margin-bottom: .85rem;
    }

    .mobile-topbar {
        display: block;
        margin: -.75rem -.75rem .85rem;
        padding: .65rem .75rem;
        background: rgba(255,255,255,.98);
        border-bottom: 1px solid var(--statsquest-card-border);
    }

    .mobile-topbar-title {
        font-size: .98rem;
        font-weight: 800;
        line-height: 1.25;
        overflow-wrap: anywhere;
    }

    .mobile-topbar-meta {
        color: #666;
        font-size: .82rem;
        margin-top: .15rem;
    }

    section[data-testid="stSidebar"] {
        min-width: min(88vw, 22rem);
    }

    div[data-testid="stHorizontalBlock"] {
        gap: .65rem;
        flex-wrap: wrap;
    }

    div[data-testid="stHorizontalBlock"] > div {
        min-width: min(100%, 16rem);
        flex: 1 1 100%;
    }

    div[data-testid="stButton"] > button,
    div[data-testid="stDownloadButton"] > button {
        width: 100%;
        min-height: 2.8rem;
        white-space: normal;
    }

    div[role="radiogroup"] label {
        min-height: 2.65rem;
        align-items: flex-start;
        padding-top: .45rem;
        padding-bottom: .45rem;
    }

    .stSlider {
        padding-left: .15rem;
        padding-right: .15rem;
    }

    iframe {
        max-width: 100%;
    }
}

@media (max-width: 700px) and (prefers-color-scheme: dark) {
    .mobile-topbar {
        background: rgba(17,24,39,.98);
        color: #f9fafb;
    }

    .mobile-topbar-meta {
        color: #d1d5db;
    }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Database-derived progress helpers
# -----------------------------
def challenge_history(pid, challenge):
    df = participant_stats(pid)
    if df.empty:
        return df
    return df.loc[df["challenge"] == challenge]

def record_completion_once(pid, level, challenge, answer):
    if answer is None or str(answer).strip() == "":
        return False
    history = challenge_history(pid, challenge)
    if not history.empty:
        return False
    add_attempt(pid, level, challenge, answer, True, 0)
    return True


# Pre/post learning assessment
# -----------------------------
# Reuses the same challenge_attempts table (level 0 = pre, level 6 = post,
# outside the 1-5 range used by real levels) so no schema change is needed.
# Always recorded at 0 XP: these are a diagnostic, not part of the game score.

def assessment_challenge_id(phase, key):
    """Challenge id for the objective knowledge quiz (ASSESSMENT_QUESTIONS).
    Only used at the "post" phase today -- there is no pre-course quiz."""
    return f"{'PRE' if phase == 'pre' else 'POST'}_{key}"

def confidence_challenge_id(phase, key):
    """Challenge id for the 1-5 confidence self-rating (CONFIDENCE_TOPIC_KEYS).
    Kept in its own namespace ("POSTSELF_" rather than "POST_") so the
    post-course confidence re-rating never collides with the post-course
    knowledge quiz -- both reuse the same topic keys (CENTER, SPREAD, ...).
    At the "pre" phase this intentionally matches assessment_challenge_id,
    since pre-course only ever has the confidence rating, not a quiz."""
    return f"{'PRE' if phase == 'pre' else 'POSTSELF'}_{key}"

def assessment_level(phase):
    return 0 if phase == "pre" else 6

def record_diagnostic_answer(pid, phase, key, answer, correct):
    """Record a single, non-retryable knowledge-quiz response."""
    challenge = assessment_challenge_id(phase, key)
    if not challenge_history(pid, challenge).empty:
        return  # already answered; diagnostic responses aren't retried
    add_attempt(pid, assessment_level(phase), challenge, answer, correct, 0)

def record_confidence_rating(pid, phase, key, answer):
    """Record a single, non-retryable confidence self-rating."""
    challenge = confidence_challenge_id(phase, key)
    if not challenge_history(pid, challenge).empty:
        return  # already answered; diagnostic responses aren't retried
    add_attempt(pid, assessment_level(phase), challenge, answer, False, 0)

def assessment_complete(pid, phase):
    """True once the knowledge quiz (ASSESSMENT_QUESTIONS) is done for this phase."""
    history = participant_stats(pid)
    if history.empty:
        return False
    answered = set(history["challenge"].unique())
    required = {assessment_challenge_id(phase, key) for key, *_ in ASSESSMENT_QUESTIONS}
    return required.issubset(answered)

def self_assessment_complete(pid, phase):
    """True once the confidence self-rating is done for this phase."""
    history = participant_stats(pid)
    if history.empty:
        return False
    answered = set(history["challenge"].unique())
    required = {confidence_challenge_id(phase, key) for key in CONFIDENCE_TOPIC_KEYS}
    return required.issubset(answered)

def assessment_score(pid, phase):
    total = len(ASSESSMENT_QUESTIONS)
    history = participant_stats(pid)
    if history.empty:
        return 0, total
    required = [assessment_challenge_id(phase, key) for key, *_ in ASSESSMENT_QUESTIONS]
    scored = history.loc[history["challenge"].isin(required) & (history["correct"] == 1)]
    return int(scored["challenge"].nunique()), total

def self_assessment_summary(pid, phase="pre"):
    total = len(CONFIDENCE_TOPIC_KEYS)
    history = participant_stats(pid)
    if history.empty:
        return None, 0, total
    required = [confidence_challenge_id(phase, key) for key in CONFIDENCE_TOPIC_KEYS]
    rows = history.loc[history["challenge"].isin(required)].copy()
    if rows.empty:
        return None, 0, total
    scores = rows["answer"].map(SELF_ASSESSMENT_VALUES).dropna()
    if scores.empty:
        return None, 0, total
    return float(scores.mean()), int(scores.count()), total

def show_confidence_review(pid, phase):
    """Card list of a participant's confidence self-ratings for one phase."""
    history = participant_stats(pid)
    if history.empty:
        return
    label = "Baseline" if phase == "pre" else "Check-out"
    st.subheader(f"{label} self-assessment review")
    for key, prompt in confidence_items(phase):
        challenge = confidence_challenge_id(phase, key)
        row = history.loc[history["challenge"] == challenge]
        if row.empty:
            continue
        answer = html.escape(str(row.iloc[-1]["answer"]))
        st.markdown(
            f"""
            <div class="level-card">
                <b>{html.escape(prompt)}</b><br>
                <span>{answer}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

def show_confidence_change(pid):
    """Baseline vs check-out confidence, side by side with the rise between them."""
    pre_avg, _, _ = self_assessment_summary(pid, "pre")
    post_avg, _, _ = self_assessment_summary(pid, "post")
    if pre_avg is None or post_avg is None:
        return
    delta = post_avg - pre_avg
    a, b, c = st.columns(3)
    a.metric("Baseline confidence", f"{pre_avg:.1f}/5")
    b.metric("Check-out confidence", f"{post_avg:.1f}/5", delta=f"{delta:+.1f}")
    c.metric("Change", f"{delta:+.1f}")

def show_assessment_review(pid, phase):
    """Review of the objective knowledge quiz (ASSESSMENT_QUESTIONS, "post" only today)."""
    history = participant_stats(pid)
    if history.empty:
        return
    phase_label = "Baseline" if phase == "pre" else "Check-out"
    st.subheader(f"{phase_label} review")
    for key, prompt, _, correct_answer in ASSESSMENT_QUESTIONS:
        challenge = assessment_challenge_id(phase, key)
        row = history.loc[history["challenge"] == challenge]
        if row.empty:
            continue
        answer = html.escape(str(row.iloc[-1]["answer"]))
        is_correct = bool(row.iloc[-1]["correct"])
        status = "Correct" if is_correct else "Not quite"
        if is_correct:
            result = f"**{status}.** You chose **{answer}**."
        else:
            result = f"**{status}.** You chose **{answer}**; the best answer is **{html.escape(str(correct_answer))}**."
        st.markdown(
            f"""
            <div class="level-card">
                <b>{html.escape(prompt)}</b><br>
                <span>{result}</span><br>
                <span class="small-muted">{html.escape(ASSESSMENT_EXPLANATIONS[key])}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# -----------------------------
# Assessment config
# -----------------------------
# Five questions mirroring the five levels, asked after Level 5 as a check-out.
# The baseline uses the same keys as a self-assessment, so completion checks and
# reporting can compare the same topics without treating the baseline as a quiz.
## Deliberately new scenarios (bakery, delivery routes, a call center, a help
# desk, a construction project) rather than restatements of the commute/
# hospital/machine/airport examples used during the levels, so the check-out
# measures transfer of the concept instead of memory of the training example.
ASSESSMENT_QUESTIONS = [
    ("CENTER", "A small bakery tracks daily sales. One holiday saw sales **ten times higher** than a normal day. Which statistic is most affected by that one unusual day?",
     ["Mean", "Median", "Mode", "Range"], "Mean"),
    ("SPREAD", "Two delivery drivers each average **30 minutes** per route. Which statistic tells you whose delivery times are more **consistent**?",
     ["Standard deviation", "Median", "Mode", "Sample size"], "Standard deviation"),
    ("DISTRIBUTION", "A call center dials **40 independent customers**; each call either connects or it doesn't. Which distribution models the **number of calls that connect**?",
     ["Binomial", "Uniform", "Exponential", "Poisson"], "Binomial"),
    ("ARRIVAL", "A help desk tracks the **time between** one customer call ending and the next one starting. Which distribution models that **waiting time**?",
     ["Exponential", "Normal", "Binomial", "Uniform"], "Exponential"),
    ("SIMULATION", "A city planner simulates **storm-water demand** thousands of times before choosing a drainage design. Why run the simulation many times?",
     ["To estimate possible outcomes and their chances", "To remove all randomness", "To guarantee the best result", "To avoid using data"],
     "To estimate possible outcomes and their chances"),
]

ASSESSMENT_EXPLANATIONS = {
    "CENTER": "The mean uses every value, so one very large value can pull it up.",
    "SPREAD": "Standard deviation tells how far values usually are from the mean.",
    "DISTRIBUTION": "Binomial counts successes across a fixed number of yes/no trials.",
    "ARRIVAL": "Exponential is used for waiting time between events.",
    "SIMULATION": "Many runs show what could happen and make the estimate steadier.",
}

# Stable internal keys for the 5 confidence topics -- these become the
# "CENTER"/"SPREAD"/... suffix in challenge ids like "PRE_CENTER". The
# *wording* students see for each topic and each scale point comes from
# content.json's assessment.pre_confidence / assessment.post_confidence
# (allowing slightly different phrasing before vs. after), matched to these
# keys purely by position -- content.json never needs to know the keys exist.
CONFIDENCE_TOPIC_KEYS = ["CENTER", "SPREAD", "DISTRIBUTION", "ARRIVAL", "SIMULATION"]

_DEFAULT_CONFIDENCE_SCALE = {
    "1": "Not comfortable yet",
    "2": "A little comfortable",
    "3": "Somewhat comfortable",
    "4": "Comfortable",
    "5": "Very comfortable",
}
_DEFAULT_CONFIDENCE_ITEMS = [
    "Using mean, median, and mode",
    "Using range, variance, and standard deviation",
    "Choosing a probability distribution for a situation",
    "Understanding random arrivals and waiting times",
    "Understanding why a simulation is run many times",
]
_DEFAULT_CONFIDENCE_PROMPT = {
    "pre": "How comfortable do you currently feel with each of these?",
    "post": "How comfortable do you feel with each of these now?",
}

def confidence_block(phase):
    section = "pre_confidence" if phase == "pre" else "post_confidence"
    block = content_get(f"assessment.{section}", {})
    return block if isinstance(block, dict) else {}

def confidence_prompt(phase):
    return confidence_block(phase).get("prompt") or _DEFAULT_CONFIDENCE_PROMPT[phase]

def confidence_scale_options(phase):
    scale = confidence_block(phase).get("scale")
    if not isinstance(scale, dict) or not scale:
        scale = _DEFAULT_CONFIDENCE_SCALE
    return [scale.get(str(n), _DEFAULT_CONFIDENCE_SCALE[str(n)]) for n in range(1, 6)]

def confidence_items(phase):
    items = confidence_block(phase).get("items")
    if not isinstance(items, list) or len(items) != len(CONFIDENCE_TOPIC_KEYS):
        items = _DEFAULT_CONFIDENCE_ITEMS
    return list(zip(CONFIDENCE_TOPIC_KEYS, items))

def confidence_value_lookup() -> dict[str, int]:
    """Maps every scale label seen across pre/post to its 1-5 score, so
    self-reported answers can be averaged even if the two phases' wording
    ever diverges slightly."""
    values: dict[str, int] = {}
    for phase in ("pre", "post"):
        for score, label in enumerate(confidence_scale_options(phase), start=1):
            values[label] = score
    return values

SELF_ASSESSMENT_VALUES = confidence_value_lookup()

# -----------------------------
# Story
# -----------------------------
STORY = {
    "intro": (
        "**Welcome to StatsQuest.** This is a short game about statistics for modeling and simulation.\n\n"
        "**Your mission:** help a simulation team make decisions from data. You will practice mean, median, mode, "
        "range, variance, standard deviation, distributions, arrivals, and Monte Carlo simulation.\n\n"
        "Start with a quick confidence check-in. Then play each level, earn XP, and unlock the next step. "
        "The final check-out shows what changed. Check-ins do not affect XP."
    ),
    "pre_assessment": (
        "Rate your confidence on five topics. This is not a quiz. It gives you a starting point to compare with the end."
    ),
    "post_assessment": (
        "Answer five check-out questions, then rate your confidence again on the same five "
        "topics from the start. That's what shows how much changed for you."
    ),
    "levels": {
        1: "Outliers can change the mean. Compare mean, median, and mode.",
        2: "Two datasets can have the same mean but different spread.",
        3: "Match each situation to the right distribution.",
        4: "Use Poisson for counts and Exponential for wait times.",
        5: "Run many simulations to see possible outcomes.",
    },
    "epilogue": (
        "Finished. You completed the statistics path and the final simulation challenge."
    ),
}

YOUTUBE_RESOURCES = {
    "home": [
        (
            "Introduction",
            "https://youtu.be/O78C5MAVdo4?si=r9XOz_fYZxkNvbs3",
            "Why statistics helps us model real systems, like airport lines and product defects.",
        ),
    ],
    "level_1": [
        (
            "Mean, median, and mode",
            "https://www.youtube.com/watch?v=5gxzPkAQdIg",
            "Reviews mean, median, and mode.",
        ),
    ],
    "level_2": [
        (
            "Range, variance, and standard deviation",
            "https://www.youtube.com/watch?v=A89FpnWX0rY",
            "Reviews range, variance, and standard deviation.",
        ),
    ],
    "level_3": [
        (
            "From data to distributions and Normal",
            "https://www.youtube.com/watch?v=A89FpnWX0rY",
            "Shows how data shapes become distributions, including the Normal curve.",
        ),
        (
            "Uniform distribution",
            "https://www.youtube.com/watch?v=2nS3ltVimyU",
            "Covers situations where every value in a range is equally likely.",
        ),
        (
            "Bernoulli and Binomial distributions",
            "https://www.youtube.com/watch?v=kI3gy6Efcew",
            "Connects one yes/no trial to counting successes across many trials.",
        ),
        (
            "Poisson distribution",
            "https://www.youtube.com/watch?v=EXoLpIwM_Qc",
            "Models event counts in a fixed time, like arrivals per 10 minutes.",
        ),
    ],
    "level_4": [
        (
            "Simulation realism",
            "https://www.youtube.com/watch?v=BELZStrWy2g",
            "Shows why random inputs make simulations more realistic.",
        ),
    ],
    "level_5": [
        (
            "Monte Carlo idea",
            "https://www.youtube.com/watch?v=Q9Gy7mkk-2A",
            "Shows why we run simulations many times.",
        ),
    ],
}

STORY = content_get("story", STORY)
if isinstance(STORY.get("levels"), dict):
    STORY["levels"] = {
        int(level): text
        for level, text in STORY["levels"].items()
        if str(level).isdigit()
    }

video_content = content_get("videos", None)
if isinstance(video_content, dict):
    YOUTUBE_RESOURCES = {
        section: [
            (
                item.get("title", ""),
                item.get("url", ""),
                item.get("description", ""),
            )
            for item in resources
        ]
        for section, resources in video_content.items()
    }

def show_youtube_resources(section_key):
    resources = YOUTUBE_RESOURCES.get(section_key, [])
    if not resources:
        return
    st.subheader(f"📺 {content_get('home.resources_label', 'Review resources')}")
    resources_description = content_get("home.resources_description", "")
    if resources_description:
        st.caption(resources_description)
    for title, url, description in resources:
        st.markdown(f"**{title}**")
        st.caption(description)
        st.video(url)

def show_formula_reference():
    formula_text = content_get(
        "formulas.home",
        r"""
Formula quick reference

**Mean:** add all values, then divide by how many values there are.  
Formula: $\bar{x} = \frac{\sum x_i}{n}$

**Median:** sort the values, then take the middle value.

**Mode:** find the value that appears most often.

**Range:** subtract the smallest value from the largest value.  
Formula: $\text{Range} = \max - \min$

**Variance:** measures spread using squared distances from the mean.  
Formula: $s^2 = \frac{\sum (x_i - \bar{x})^2}{n - 1}$

**Standard deviation:** take the square root of variance.  
Formula: $s = \sqrt{s^2}$
"""
    )
    title, body = split_markdown_title(formula_text, "Formula quick reference")
    st.subheader(title)
    st.markdown(body)

def show_level_1_formulas():
    formula_text = content_get(
        "formulas.level_1",
        r"""
Level 1 formulas

**Mean:** add all values, then divide by the number of values.  
Formula: $\bar{x} = \frac{\sum x_i}{n}$

**Median:** sort the values, then take the middle value.

**Mode:** find the value that appears most often.

**Range:** subtract the smallest value from the largest value.  
Formula: $\text{Range} = \max - \min$

**Variance:** measures squared distance from the mean.  
Formula: $s^2 = \frac{\sum (x_i - \bar{x})^2}{n - 1}$

**Standard deviation:** take the square root of variance.  
Formula: $s = \sqrt{s^2}$
"""
    )
    title, body = split_markdown_title(formula_text, "Level 1 formulas")
    st.subheader(title)
    st.markdown(body)

def show_level_2_formulas():
    formula_text = content_get(
        "formulas.level_2",
        r"""
Level 2 formulas

**Range:** subtract the smallest value from the largest value.  
Formula: $\text{Range} = \max - \min$

**Variance:** measures spread using squared distances from the mean.  
Formula: $s^2 = \frac{\sum (x_i - \bar{x})^2}{n - 1}$

**Standard deviation:** take the square root of variance.  
Formula: $s = \sqrt{s^2}$
"""
    )
    title, body = split_markdown_title(formula_text, "Level 2 formulas")
    st.subheader(title)
    st.markdown(body)

def show_level_4_formulas():
    formula_text = content_get(
        "formulas.level_4",
        r"""
Need a formula?

**Poisson — number of arrivals:**
Formula: $P(X = k) = \dfrac{\lambda^k e^{-\lambda}}{k!}$

**Exponential — time between arrivals:**
Formula: $f(t) = \lambda e^{-\lambda t}$, mean wait $= \dfrac{1}{\lambda}$
"""
    )
    title, body = split_markdown_title(formula_text, "Need a formula?")
    st.subheader(title)
    st.markdown(body)

def show_distribution_reference():
    st.subheader("Distribution quick reference")
    distribution_df = pd.DataFrame(
        [
            ("Normal", "Values cluster around an average", "sensor noise", "Mean, standard deviation"),
            ("Uniform", "All values in a range are equally likely", "random position from 0 to 100", "Minimum, maximum"),
            ("Bernoulli", "One yes/no or success/failure trial", "one item defective or not defective", "Success probability p"),
            ("Binomial", "Number of successes in fixed trials", "defects in a batch of 20", "Trials n, probability p"),
            ("Poisson", "Number of events in a fixed time", "passengers in 10 minutes", "Average rate"),
            ("Exponential", "Time between events", "time until next passenger", "Rate, mean wait"),
        ],
        columns=["Distribution", "Use when", "Example", "Key parameter"],
    )
    st.dataframe(distribution_df, hide_index=True, width="stretch")

def show_descriptive_stats(data, *, label_prefix=""):
    values = np.array(data)
    counts = pd.Series(values).value_counts()
    if counts.empty or counts.max() == 1:
        mode_display = "No repeated mode"
    else:
        most_common: pd.Series = counts.loc[counts == counts.max()]
        modes = sorted(most_common.index.tolist())
        mode_display = ", ".join(str(int(mode)) for mode in modes)
    labels = [
        ("Mean", f"{values.mean():.2f}"),
        ("Median", f"{np.median(values):.2f}"),
        ("Mode", mode_display),
        ("Range", f"{values.max() - values.min():.2f}"),
        ("Variance", f"{values.var(ddof=1):.2f}"),
        ("Std. deviation", f"{values.std(ddof=1):.2f}"),
    ]
    for row_start in range(0, len(labels), 3):
        columns = st.columns(3)
        for column, (name, value) in zip(columns, labels[row_start:row_start + 3]):
            column.metric(f"{label_prefix}{name}", value)

def show_how_to_play():
    st.subheader("How to play")
    st.info(
        "Start with the Starting Check-In, then work through each level in order: "
        "Watch a short video, then work through Explore, Try, and Apply. "
        "You get two scoring tries for each required question. First try earns full XP. "
        "Second try earns partial XP. After two wrong tries, keep trying until it is correct so the next page opens. "
        "Bonus questions are optional make-up XP."
    )

def personal_goal_required():
    goal_setting = content_get("assessment.goal_setting", {})
    goal_options = goal_setting.get("options", []) if isinstance(goal_setting, dict) else []
    return bool(goal_options)

def personal_goal_complete():
    if not personal_goal_required():
        return True
    goal = st.session_state.get("learning_goal_choice") or st.session_state.get("learning_goal")
    if goal:
        return True
    pid = st.session_state.get("pid")
    if not pid:
        return False
    return not challenge_history(pid, "SRL_GOAL").empty

def go_to_next_page():
    current = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    next_page = navigation.next_page(current)
    if next_page is None:
        return
    if current == "🏠 Home" and not personal_goal_complete():
        set_answer_feedback("warning", "Choose a personal goal before moving to the Starting Check-In.")
        return
    if current == "🧭 Starting Check-In" and not self_assessment_complete(st.session_state.pid, "pre"):
        set_answer_feedback("warning", "Complete all 5 baseline self-ratings before heading out.")
        return
    if current == "📊 Final Check-Out" and not assessment_complete(st.session_state.pid, "post"):
        set_answer_feedback("warning", "Answer all 5 check-out questions before moving on.")
        return
    if current == "📊 Final Check-Out" and not self_assessment_complete(st.session_state.pid, "post"):
        set_answer_feedback("warning", "Rate your confidence again before moving on — that's what shows your progress.")
        return
    current_level = PAGE_LEVELS.get(current)
    if current_level and not level_complete(st.session_state.pid, current_level):
        answered, total, pending = level_progress(st.session_state.pid, current_level)
        set_answer_feedback(
            "warning",
            f"Complete this level before moving on. Required steps complete: {answered}/{total}. Pending: {challenge_labels(pending)}.",
        )
        return
    if not page_accessible(st.session_state.pid, next_page):
        first_incomplete = first_incomplete_page(st.session_state.pid)
        st.session_state.selected_page = first_incomplete
        set_answer_feedback("warning", "You need to answer all earlier level questions correctly before moving ahead.")
        return
    st.session_state.answer_feedback = None
    st.session_state.selected_page = next_page

def go_to_previous_page():
    current = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    previous = navigation.previous_page(current)
    if previous is None:
        return
    st.session_state.answer_feedback = None
    st.session_state.selected_page = previous

def show_next_button():
    current = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    previous_page = navigation.previous_page(current)
    next_page = navigation.next_page(current)
    # Shown here, right above Back/Next, rather than at the top of the page:
    # this feedback exists because of something the student did with these
    # buttons (or a redirect while trying to navigate), so it belongs where
    # their attention already is instead of requiring a scroll to the top.
    show_answer_feedback()
    if previous_page is None and next_page is None:
        return
    st.divider()
    back_col, next_col = st.columns(2)
    if previous_page:
        back_col.button(f"Back: {previous_page}", on_click=go_to_previous_page, width="stretch")
    if next_page:
        next_label = f"Start the game: {next_page}" if next_page.startswith("🎯 Level 1") else f"Next: {next_page}"
        next_col.button(next_label, type="primary", on_click=go_to_next_page, width="stretch")

def show_boss_progress(xp):
    defeated = boss_defeated_percent(xp)
    st.progress(min(1.0, xp / PERFECT_SCORE), text=f"Final challenge progress: {defeated}%")
    if xp >= PERFECT_SCORE:
        st.success(f"👑 Perfect score: {xp}/{PERFECT_SCORE} XP. All challenges complete.")
    else:
        st.info(f"Progress: {defeated}% ({xp}/{PERFECT_SCORE} XP). Get all XP for a perfect score.")

def correct_challenges(pid):
    history = participant_stats(pid)
    if history.empty:
        return set()
    return set(history.loc[history["correct"] == 1, "challenge"].tolist())

def level_progress(pid, level):
    """Progress against the level's REQUIRED challenges only — the bonus
    challenge is optional make-up credit and doesn't gate completion."""
    required = LEVEL_REQUIRED_CHALLENGES[level]
    correct = correct_challenges(pid)
    answered = [challenge for challenge in required if challenge in correct]
    pending = [challenge for challenge in required if challenge not in correct]
    return len(answered), len(required), pending

def level_bonus_challenge(level):
    """The single optional bonus challenge id for a level, or None."""
    required = set(LEVEL_REQUIRED_CHALLENGES[level])
    bonus_ids = [c for c in LEVEL_CHALLENGES[level] if c not in required]
    return bonus_ids[0] if bonus_ids else None

def level_has_wrong_required_attempt(pid, level):
    """True once the player has gotten at least one required question in
    this level wrong. The bonus challenge exists to make up for exactly
    that lost XP, so it only unlocks once there's something to make up."""
    history = participant_stats(pid)
    if history.empty:
        return False
    required = list(LEVEL_REQUIRED_CHALLENGES[level])
    wrong = history.loc[history["challenge"].isin(required) & (history["correct"] == 0)]
    return not wrong.empty

def challenge_xp_missed(pid, challenge):
    base = CHALLENGE_POINTS.get(challenge, 0)
    if base == 0:
        return 0
    history = challenge_history(pid, challenge)
    if history.empty:
        return 0
    earned_points = pd.Series(history["points"])
    earned = int(earned_points.max())
    return max(0, base - earned)

def level_missed_required_xp(pid, level):
    return sum(challenge_xp_missed(pid, challenge) for challenge in LEVEL_REQUIRED_CHALLENGES[level])

def level_bonus_remaining_xp(pid, level):
    bonus_id = level_bonus_challenge(level)
    if bonus_id is None:
        return 0
    bonus_base = CHALLENGE_POINTS.get(bonus_id, 0)
    bonus_earned = 0
    history = challenge_history(pid, bonus_id)
    if not history.empty:
        bonus_points = pd.Series(history["points"])
        bonus_earned = int(bonus_points.max())
    return max(0, min(level_missed_required_xp(pid, level), bonus_base - bonus_earned))

def bonus_unlocked(pid, level):
    """Unlocked once a required question in this level has been missed, or
    once the bonus itself already has an attempt on record (so it doesn't
    vanish mid-attempt if later required answers all end up correct)."""
    bonus_id = level_bonus_challenge(level)
    if bonus_id is None:
        return False
    if level_has_wrong_required_attempt(pid, level):
        return True
    return not challenge_history(pid, bonus_id).empty

def level_complete(pid, level):
    answered, total, _ = level_progress(pid, level)
    return answered == total

def first_incomplete_level(pid):
    for level in sorted(LEVEL_CHALLENGES):
        if not level_complete(pid, level):
            return level
    return None

def first_incomplete_page(pid):
    if not self_assessment_complete(pid, "pre"):
        return "🧭 Starting Check-In" if personal_goal_complete() else "🏠 Home"
    level = first_incomplete_level(pid)
    if level is None:
        checkout_done = assessment_complete(pid, "post") and self_assessment_complete(pid, "post")
        return "📊 Final Check-Out" if not checkout_done else "🥇 Leaderboard"
    for page, page_level in PAGE_LEVELS.items():
        if page_level == level:
            return page
    return "🏠 Home"

def page_accessible(pid, page):
    if page == "🏠 Home":
        return True
    if page == "🧭 Starting Check-In":
        return personal_goal_complete()
    if not self_assessment_complete(pid, "pre"):
        return False  # the baseline check-in comes before everything else
    level = PAGE_LEVELS.get(page)
    if level is not None:
        return all(level_complete(pid, earlier) for earlier in range(1, level))
    if page == "📊 Final Check-Out":
        return level_complete(pid, 5)
    if page == "🥇 Leaderboard":
        return (
            first_incomplete_level(pid) is None
            and assessment_complete(pid, "post")
            and self_assessment_complete(pid, "post")
        )
    return False

def enforce_page_access(pid):
    """Must be called before the `selected_page`-keyed radio widget is
    instantiated this run — Streamlit forbids writing to a widget's bound
    session_state key after that widget has already rendered in the same run."""
    selected_page = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    if page_accessible(pid, selected_page):
        return
    fallback = first_incomplete_page(pid)
    st.session_state.selected_page = fallback
    set_answer_feedback("warning", "You need to answer all earlier level questions correctly before moving ahead.")
    st.rerun()

def show_level_progress(pid, level):
    required = LEVEL_REQUIRED_CHALLENGES[level]
    correct = correct_challenges(pid)
    answered_items = [challenge for challenge in required if challenge in correct]
    pending = [challenge for challenge in required if challenge not in correct]
    answered = len(answered_items)
    total = len(required)
    progress_col, _ = st.columns([1, 2])
    with progress_col:
        st.progress(answered / total, text=f"Required steps complete: {answered}/{total}")
        if answered_items:
            st.caption(f"Completed: {challenge_labels(answered_items)}")
        if pending:
            st.caption(f"Pending: {challenge_labels(pending)}")
        else:
            st.success("Level complete. You can move to the next page.")

        bonus_id = level_bonus_challenge(level)
        if bonus_id:
            missed_xp = level_missed_required_xp(pid, level)
            bonus_remaining = level_bonus_remaining_xp(pid, level)
            if missed_xp > 0:
                st.caption(f"Missed XP from required questions: {missed_xp}. Make-up XP still available here: {bonus_remaining}.")
            if bonus_id in correct:
                st.caption(f"🎁 Bonus complete: {challenge_label(bonus_id)} (+XP earned)")
            elif bonus_unlocked(pid, level):
                st.caption(f"🎁 Bonus unlocked: {challenge_label(bonus_id)} — a chance to earn back up to {bonus_remaining} XP.")
            else:
                st.caption(f"🎁 Bonus challenge locked — it unlocks if you miss a question above.")

def set_answer_feedback(kind, message, challenge=None):
    st.session_state.answer_feedback = {
        "kind": kind,
        "message": message,
        "page": st.session_state.get("selected_page"),
        "challenge": challenge,
    }

def show_answer_feedback():
    feedback = st.session_state.get("answer_feedback")
    if not feedback:
        return
    if feedback.get("page") != st.session_state.get("selected_page"):
        st.session_state.answer_feedback = None
        return
    if feedback.get("challenge"):
        return
    kind = feedback.get("kind")
    message = feedback.get("message", "")
    if kind == "success":
        st.success(message)
    elif kind == "warning":
        st.warning(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)

def shuffled_options(key, options):
    """Stable per-user option order so answers are randomized without rerun jitter."""
    shuffled = list(options)
    seed = f"{st.session_state.get('pid', 'anonymous')}|{key}"
    random.Random(seed).shuffle(shuffled)
    return shuffled

def answer_radio(label, options, key, **kwargs):
    kwargs.setdefault("index", None)
    return st.radio(label, shuffled_options(key, options), key=key, **kwargs)

def show_optional_hint(challenge, default_text=None):
    """A student-requested hint, shown only if they open it. Used on the Try
    stage of each level (Explore has visible support already on the page;
    Apply has none)."""
    hint = content_get(f"hints.{challenge}", default_text)
    if not hint:
        return
    with st.expander("💡 Need a hint?"):
        st.markdown(hint)

def inline_status_html(message):
    safe = html.escape(str(message))
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    return safe.replace("\n\n", "<br><br>").replace("\n", "<br>")

def show_challenge_status_box(status, title, message):
    st.markdown(
        f"""
        <div class="challenge-status challenge-status-{status}">
            <div class="challenge-status-title">{html.escape(title)}</div>
            <div>{inline_status_html(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------
# Shared level-page building blocks
# -----------------------------
# Every level_pages/level_N.py page follows the same Watch/Explore/Try/Apply
# shape, so the pieces of that shape live here once instead of being
# reimplemented (and drifting) in each level file.

def is_stage_complete(pid, challenge):
    return challenge in correct_challenges(pid)

def show_step_header(title, body=None):
    st.subheader(title)
    if body:
        st.write(body)

def show_scenario_card(title, story, values=None):
    value_line = f"<code>{html.escape(', '.join(str(v) for v in values))}</code>" if values is not None else ""
    st.markdown(
        f"""
        <div class="level-card">
            <b>{html.escape(title)}</b><br>
            <span>{html.escape(story)}</span><br>
            {value_line}
        </div>
        """,
        unsafe_allow_html=True,
    )

def show_record_status(recorded, done_title, pending_title, done_message, pending_message):
    if recorded:
        show_challenge_status_box("correct", done_title, done_message)
    else:
        show_challenge_status_box("unanswered", pending_title, pending_message)

def prominent_control_label(label):
    safe_label = str(label).replace("]", r"\]")
    return f":blue-background[{safe_label}]"

def show_video_acknowledgement(pid, level, video_challenge_id, key):
    """Renders the 'I watched the video' checkbox, records it (0 XP) the
    first time it's checked, and returns whether Step 1 - Watch is done."""
    watched = st.checkbox(
        ":yellow-background[I watched the video and am ready to continue.]",
        value=is_stage_complete(pid, video_challenge_id),
        key=key,
    )
    if watched:
        record_completion_once(pid, level, video_challenge_id, f"Watched Level {level} video")
    return is_stage_complete(pid, video_challenge_id)

def show_challenge_acknowledgement(pid, challenge):
    feedback = st.session_state.get("answer_feedback")
    if (
        feedback
        and feedback.get("page") == st.session_state.get("selected_page")
        and feedback.get("challenge") == challenge
    ):
        kind = feedback.get("kind")
        message = feedback.get("message", "")
        if kind == "success":
            show_challenge_status_box("correct", "Answered correctly", message)
        elif kind == "warning":
            history = challenge_history(pid, challenge)
            wrong_count = len(history.loc[history["correct"] == 0]) if not history.empty else 1
            status = "two-wrong" if wrong_count >= MAX_WRONG_ATTEMPTS else "one-wrong"
            title = "Second wrong attempt" if status == "two-wrong" else "One wrong attempt"
            show_challenge_status_box(status, title, message)
        elif kind == "error":
            show_challenge_status_box("two-wrong", "Second wrong attempt", message)
        else:
            show_challenge_status_box("info", "Challenge status", message)
        st.session_state.answer_feedback = None
        return

    history = challenge_history(pid, challenge)
    if history.empty:
        show_challenge_status_box(
            "unanswered",
            "Unanswered",
            f"{challenge_label(challenge)} has not been answered yet.",
        )
        return

    correct_rows = history.loc[history["correct"] == 1]
    if not correct_rows.empty:
        row = correct_rows.iloc[-1]
        points = int(row["points"])
        answer = row["answer"]
        if points > 0:
            show_challenge_status_box(
                "correct",
                "Answered correctly",
                f"{challenge_label(challenge)}. You earned {points} XP. Your answer: {answer}.",
            )
        else:
            show_challenge_status_box(
                "correct",
                "Answered correctly",
                f"{challenge_label(challenge)} is complete. No XP was left for this try. Your answer: {answer}.",
            )
        return

    attempts_used = len(history)
    attempts_left = max(0, MAX_WRONG_ATTEMPTS - attempts_used)
    latest_answer = history.iloc[-1]["answer"]
    if attempts_used >= MAX_WRONG_ATTEMPTS:
        show_challenge_status_box(
            "two-wrong",
            "Second wrong attempt",
            f"Scoring tries used for {challenge_label(challenge)}. Last answer: {latest_answer}. "
            "Keep trying to complete the question.",
        )
    else:
        show_challenge_status_box(
            "one-wrong",
            "One wrong attempt",
            f"Attempt recorded for {challenge_label(challenge)}. Last answer: {latest_answer}. "
            f"{attempts_left} scoring try/tries left.",
        )

def format_correct_feedback(message, explanation=None):
    if explanation:
        return f"{message}\n\n**Why:** {explanation}"
    return message

def format_wrong_feedback(message, answer, correct_answer=None, explanation=None):
    details = []
    if answer is not None and correct_answer is not None:
        details.append(f"You chose **{answer}**. The best answer is **{correct_answer}**.")
    elif answer is not None:
        details.append(f"**{answer}** is not the best choice here.")
    if explanation:
        details.append(f"**Why:** {explanation}")
    if details:
        return f"{message}\n\n" + "\n\n".join(details)
    return message

STAGE_LABELS = {"explore": "Explore", "try": "Try", "apply": "Apply"}


def clear_student_runtime_state():
    """Clear per-browser answers/progress controls; database rows remain authoritative."""
    keep = {"logged", "is_admin", "pid", "first_name", "last_name", "admin_pw_input"}
    prefixes = ("l1", "l2", "l4", "l5", "L3_", "pre_", "post_", "postself_")
    exact_keys = {
        "selected_page",
        "last_selected_page",
        "learning_goal",
        "learning_goal_choice",
        "answer_feedback",
    }
    for key in list(st.session_state.keys()):
        if key in keep:
            continue
        if key in exact_keys or (isinstance(key, str) and key.startswith(prefixes)):
            del st.session_state[key]


def log_out_student(message=None):
    clear_student_runtime_state()
    st.session_state.logged = False
    st.session_state.is_admin = False
    st.session_state.pid = ""
    st.session_state.first_name = ""
    st.session_state.last_name = ""
    if message:
        st.session_state.logout_message = message

def score_answer(pid, level, challenge, answer, correct, base=20, correct_answer=None, explanation=None, stage=None):
    """`stage` (None, "explore", "try", or "apply") controls whether a wrong
    *non-final* attempt reveals the correct answer. Per the faded-scaffolding
    spec, no stage should hand over the answer before scoring attempts are
    exhausted -- Explore gets targeted-but-non-revealing feedback, Try adds
    an optional on-request hint elsewhere on the page, Apply gets only a
    bare retry prompt. `stage=None` (bonus questions, and any question not
    yet part of a staged level) keeps the original immediate-reveal
    behavior. The correct answer and explanation are always shown once
    scoring attempts are exhausted, regardless of stage."""
    if answer is None or str(answer).strip() == "":
        message = "Choose an answer before submitting."
        set_answer_feedback("warning", message, challenge=challenge)
        show_challenge_status_box("one-wrong", "Answer required", message)
        return

    history = challenge_history(pid, challenge)

    if not history.empty and (history["correct"] == 1).any():
        message = "You've already scored this challenge."
        set_answer_feedback("info", message, challenge=challenge)
        show_challenge_status_box("info", "Challenge status", message)
        return

    if challenge.endswith("_BONUS"):
        base = min(base, level_bonus_remaining_xp(pid, level))

    wrong_so_far = len(history)  # every recorded attempt here is a wrong one
    attempt_number = wrong_so_far + 1
    is_final_attempt = attempt_number == MAX_WRONG_ATTEMPTS

    if correct:
        if is_final_attempt:
            points = max(5, int(base * CONSOLATION_FRACTION)) if base > 0 else 0
            recorded = add_attempt(pid, level, challenge, answer, True, points)
            if points > 0:
                success_message = format_correct_feedback(f"✅ Correct! +{points} XP (partial credit)", explanation)
            else:
                success_message = format_correct_feedback("✅ Correct! This step is complete.", explanation)
        elif attempt_number > MAX_WRONG_ATTEMPTS:
            recorded = add_attempt(pid, level, challenge, answer, True, 0)
            if base > 0:
                success_message = format_correct_feedback("✅ Correct! No XP was left, but the question is complete.", explanation)
            else:
                success_message = format_correct_feedback("✅ Correct! This step is complete.", explanation)
        else:
            recorded = add_attempt(pid, level, challenge, answer, True, base)
            if base > 0:
                success_message = format_correct_feedback(f"✅ Correct! +{base} XP", explanation)
            else:
                success_message = format_correct_feedback("✅ Correct! This step is complete.", explanation)

        if recorded:
            set_answer_feedback("success", success_message, challenge=challenge)
        else:
            # A concurrent submit (e.g. a fast double-click) already scored
            # this challenge first — idx_one_correct_per_challenge rejected
            # this insert, so nothing was double-counted.
            set_answer_feedback("info", "You've already scored this challenge.", challenge=challenge)
        st.rerun()
    else:
        add_attempt(pid, level, challenge, answer, False, 0)
        remaining = MAX_WRONG_ATTEMPTS - attempt_number
        if remaining > 0:
            if base > 0:
                consolation = max(5, int(base * CONSOLATION_FRACTION))
                retry_message = (
                    f"❌ Not quite. {remaining} scoring try/tries left. "
                    f"A correct answer next time earns partial credit (+{consolation} XP)."
                )
            else:
                retry_message = f"❌ Not quite. {remaining} try/tries left. Choose the best answer to complete this step."
            if stage in STAGE_LABELS:
                # Withhold the answer while tries remain -- this is what
                # keeps Explore/Try/Apply an actual first attempt instead of
                # a reveal-then-retry loop.
                if stage == "try":
                    retry_message += " Use the hint on this page if you'd like one."
                message = format_wrong_feedback(retry_message, answer)
            else:
                message = format_wrong_feedback(retry_message, answer, correct_answer, explanation)
            set_answer_feedback("warning", message, challenge=challenge)
            show_challenge_status_box("one-wrong", "One wrong attempt", message)
        else:
            reveal = f" The correct answer was **{correct_answer}**." if correct_answer is not None else ""
            if base > 0:
                retry_message = f"❌ Not quite. No scoring tries are left, so this question is now worth 0 XP.{reveal} Keep trying until it is correct."
            else:
                retry_message = f"❌ Not quite.{reveal} Keep trying until it is correct."
            message = format_wrong_feedback(retry_message, answer, correct_answer, explanation)
            set_answer_feedback("error", message, challenge=challenge)
            show_challenge_status_box("two-wrong", "Second wrong attempt", message)


def admin_completion_summary(participants_df, attempts_df):
    """One row per participant showing score and stage completion by level."""
    if participants_df.empty:
        return pd.DataFrame()

    total_required = sum(len(challenges) for challenges in LEVEL_REQUIRED_CHALLENGES.values())
    rows = []
    for _, participant in participants_df.iterrows():
        pid = participant["PID"]
        attempts = attempts_df.loc[attempts_df["PID"] == pid] if not attempts_df.empty else attempts_df
        correct = set(attempts.loc[attempts["correct"] == 1, "challenge"].tolist()) if not attempts.empty else set()
        xp = int(pd.Series(attempts["points"]).sum()) if not attempts.empty else 0

        required_done = sum(
            1
            for challenges in LEVEL_REQUIRED_CHALLENGES.values()
            for challenge in challenges
            if challenge in correct
        )
        row = {
            "Name": f"{participant['First name']} {participant['Last name']}",
            "PIN": participant["PIN"],
            "XP": xp,
            "Required complete": f"{required_done}/{total_required}",
            "Overall": "Complete" if required_done == total_required else "In progress",
        }

        for level, challenges in LEVEL_REQUIRED_CHALLENGES.items():
            by_stage = {"watch": [], "explore": [], "try": [], "apply": [], "complete": []}
            for challenge in challenges:
                meta = CHALLENGE_META.get(challenge, {})
                stage = meta.get("stage") or "complete"
                if stage in by_stage:
                    by_stage[stage].append(challenge)

            stage_parts = []
            for stage in ("watch", "explore", "try", "apply", "complete"):
                stage_challenges = by_stage[stage]
                if not stage_challenges:
                    continue
                done = sum(1 for challenge in stage_challenges if challenge in correct)
                label = stage.title()
                stage_parts.append(f"{label} {done}/{len(stage_challenges)}")
            level_done = all(challenge in correct for challenge in challenges)
            row[f"Level {level}"] = "Done" if level_done else "; ".join(stage_parts)

        rows.append(row)

    return pd.DataFrame(rows)


# -----------------------------
# Login
# -----------------------------
for key, default in {
    "logged": False,
    "is_admin": False,
    "pid": "",
    "first_name": "",
    "last_name": "",
    "learning_goal": "",
    "answer_feedback": None,
    "last_selected_page": "",
    "logout_message": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

try:
    ensure_schema()
except Exception as schema_error:
    show_database_error(str(schema_error))

if (
    st.session_state.logged
    and not st.session_state.is_admin
    and st.session_state.pid
    and not participant_exists(st.session_state.pid)
):
    log_out_student("Your participant record was removed by the instructor. Register again to start fresh.")
    st.rerun()

if not st.session_state.logged:
    st.markdown('<div class="game-title">🎮 StatsQuest</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="game-subtitle">An individual statistics self-assessment for Modeling & Simulation</div>',
        unsafe_allow_html=True
    )

    st.markdown(STORY["intro"])

    if st.session_state.logout_message:
        st.info(st.session_state.logout_message)
        st.session_state.logout_message = None

    st.info(
        "Enter your name and a 4-digit PIN. Use the same name and PIN later to resume."
    )

    c1, c2 = st.columns(2)
    first = c1.text_input("First name", placeholder="Joe")
    last = c2.text_input("Last name", placeholder="Smith")
    pin = st.text_input("Choose a 4-digit PIN", placeholder="1234", max_chars=4, type="password")

    if st.button(f"🚀 {content_get('home.start_button', 'Start StatsQuest')}", type="primary", width="stretch"):
        if not first.strip() or not last.strip():
            st.warning("Enter your first and last name.")
        elif not pin.strip().isdigit() or len(pin.strip()) != 4:
            st.warning("Your PIN must be exactly 4 digits.")
        else:
            registered = False
            try:
                candidate_pid = make_pid(first, last, pin.strip())
                existing_pid = find_participant_pid_by_name(first, last)
                if existing_pid and existing_pid != candidate_pid:
                    st.error(
                        "That name is already registered with a different PIN. "
                        "Enter the PIN you used the first time to resume your progress "
                        "(if you're a different person with the same name, add a middle "
                        "initial or ask your instructor for help)."
                    )
                else:
                    new_pid, fn, ln = register_participant(first, last, pin.strip())
                    clear_student_runtime_state()
                    st.session_state.pid = new_pid
                    st.session_state.first_name = fn
                    st.session_state.last_name = ln
                    st.session_state.selected_page = first_incomplete_page(new_pid)
                    st.session_state.logged = True
                    registered = True
            except Exception as registration_error:
                # show_database_error() calls st.stop() itself; kept out of
                # the st.rerun() path below so a successful rerun is never
                # accidentally caught by this except clause.
                show_database_error(str(registration_error))
            if registered:
                st.rerun()

    with st.expander("🛠️ Instructor / Admin access"):
        if not ADMIN_ACCESS_ENABLED:
            st.info(
                "Admin access is disabled — no STATSQUEST_ADMIN_PASSWORD secret is set. "
                "Set that secret to enable the instructor dashboard."
            )
        else:
            admin_pw = st.text_input("Admin password", type="password", key="admin_pw_input")
            if st.button("Enter Admin Dashboard"):
                if hmac.compare_digest(admin_pw, ADMIN_PASSWORD):
                    st.session_state.logged = True
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("Incorrect admin password.")

    st.stop()

# -----------------------------
# Admin Dashboard
# -----------------------------
if st.session_state.is_admin:
    with st.sidebar:
        st.markdown("## 🛠️ Admin")
        if st.button("Log out"):
            st.session_state.logged = False
            st.session_state.is_admin = False
            st.rerun()

    st.markdown('<div class="game-title">🛠️ StatsQuest Admin Dashboard</div>', unsafe_allow_html=True)
    st.caption("Instructor view — every participant's score and full attempt history.")

    if CONTENT_ISSUES:
        st.warning(
            f"⚠️ content.json is missing required section(s): {', '.join(CONTENT_ISSUES)}. "
            "The app is falling back to built-in defaults for that copy — check that "
            "content.json exists next to app.py and is valid JSON."
        )

    if not db.USE_POSTGRES:
        st.warning(
            "⚠️ No `DATABASE_URL` secret is configured, so this app is using local file "
            "storage (`stats_game.db`) instead of Postgres. That does not persist reliably "
            "on most hosting platforms, including Streamlit Community Cloud — scores can be "
            "lost on restart, or writes can fail outright. If this app is deployed anywhere "
            "other than your own machine, add `DATABASE_URL` under **Settings → Secrets** "
            "before sharing it with students."
        )

    board = leaderboard()
    st.subheader("🥇 Leaderboard")
    if board.empty:
        st.info("No participants yet.")
    else:
        admin_board = board.drop(columns=["PID"])
        st.dataframe(admin_board, hide_index=True, width="stretch")
        st.download_button(
            "⬇️ Download leaderboard (CSV)",
            csv_safe_export(admin_board, ["Name"]).to_csv(index=False).encode("utf-8"),
            "statsquest_leaderboard.csv",
            "text/csv",
        )

    st.subheader("👤 Participants")
    st.caption(
        "Look someone up if they forgot their PIN — this table (and its CSV) is only "
        "visible here, never to other students."
    )
    participants_df = all_participants()
    if participants_df.empty:
        st.info("No participants yet.")
    else:
        name_filter = st.text_input("Filter by name", key="admin_participant_filter", placeholder="e.g. Smith")
        filtered_participants = participants_df
        if name_filter.strip():
            needle = name_filter.strip().lower()
            name_mask = (
                participants_df["First name"].str.lower().str.contains(needle, regex=False)
                | participants_df["Last name"].str.lower().str.contains(needle, regex=False)
            )
            filtered_participants = participants_df.loc[name_mask]
        st.dataframe(filtered_participants.drop(columns=["PID"]), hide_index=True, width="stretch")
        st.download_button(
            "⬇️ Download participants (CSV)",
            csv_safe_export(filtered_participants.drop(columns=["PID"]), ["First name", "Last name"]).to_csv(index=False).encode("utf-8"),
            "statsquest_participants.csv",
            "text/csv",
        )

        st.subheader("🧹 Manage participant records")
        st.caption("Reset scores keeps the name/PIN login. Delete participant removes the student and all attempt history.")
        participant_options = {
            f"{row['First name']} {row['Last name']} — PIN {row['PIN']}": row["PID"]
            for _, row in participants_df.iterrows()
        }
        selected_participant_label = st.selectbox(
            "Participant",
            list(participant_options),
            key="admin_manage_participant",
        )
        selected_pid = participant_options[selected_participant_label]
        confirm_text = st.text_input(
            "Type RESET or DELETE to confirm",
            key="admin_manage_confirm",
            placeholder="RESET or DELETE",
        )
        reset_col, delete_col = st.columns(2)
        if reset_col.button("Reset this participant's scoring", width="stretch"):
            if confirm_text.strip().upper() != "RESET":
                st.warning("Type RESET before resetting this participant's scoring.")
            else:
                reset_participant_attempts(selected_pid)
                st.success(f"Scoring reset for {selected_participant_label}.")
                st.rerun()
        if delete_col.button("Delete this participant", type="primary", width="stretch"):
            if confirm_text.strip().upper() != "DELETE":
                st.warning("Type DELETE before deleting this participant.")
            else:
                delete_participant(selected_pid)
                st.success(f"Deleted {selected_participant_label}.")
                st.rerun()

    st.subheader("📜 Full attempt log")
    c = conn()
    log = c.read_sql("""
        SELECT p.pid AS "PID",
               p.first_name || ' ' || p.last_name AS "Name",
               a.level, a.challenge, a.answer, a.correct, a.points, a.created_at
        FROM challenge_attempts a
        JOIN participants p ON p.pid = a.pid
        ORDER BY a.created_at
    """)
    c.close()
    if log.empty:
        st.info("No attempts recorded yet.")
    else:
        st.dataframe(log.drop(columns=["PID"]), hide_index=True, width="stretch")
        st.download_button(
            "⬇️ Download attempt log (CSV)",
            csv_safe_export(log.drop(columns=["PID"]), ["Name", "answer"]).to_csv(index=False).encode("utf-8"),
            "statsquest_attempts.csv",
            "text/csv",
        )

    st.subheader("✅ Completion status")
    completion = admin_completion_summary(participants_df, log)
    if completion.empty:
        st.info("No participants yet.")
    else:
        st.dataframe(completion, hide_index=True, width="stretch")
        st.download_button(
            "⬇️ Download completion status (CSV)",
            csv_safe_export(completion, ["Name"]).to_csv(index=False).encode("utf-8"),
            "statsquest_completion_status.csv",
            "text/csv",
        )

    st.subheader("📈 Self-assessment and check-out")
    # "POST_" is the check-out knowledge quiz (right/wrong); "POSTSELF_" is
    # the check-out confidence re-rating (1-5 scale) -- kept in a separate
    # challenge-id namespace specifically so this table can show a real
    # confidence rise instead of conflating a quiz score with a confidence
    # rating, which look similar but measure different things.
    diag = log.loc[log["challenge"].str.startswith(("PRE_", "POST_", "POSTSELF_"))].copy() if not log.empty else log
    if diag.empty:
        st.info("No baseline or check-out responses recorded yet.")
    else:
        baseline = diag.loc[diag["challenge"].str.startswith("PRE_")].copy()
        baseline["Confidence"] = baseline["answer"].map(SELF_ASSESSMENT_VALUES)
        baseline_summary = (
            baseline.dropna(subset=["Confidence"])
            .groupby("Name")
            .agg(**{"Baseline confidence": ("Confidence", "mean")})
        )

        post_confidence = diag.loc[diag["challenge"].str.startswith("POSTSELF_")].copy()
        post_confidence["Confidence"] = post_confidence["answer"].map(SELF_ASSESSMENT_VALUES)
        post_confidence_summary = (
            post_confidence.dropna(subset=["Confidence"])
            .groupby("Name")
            .agg(**{"Check-out confidence": ("Confidence", "mean")})
        )

        checkout_summary = (
            diag.loc[(diag["challenge"].str.startswith("POST_")) & (diag["correct"] == 1)]
            .groupby("Name")["challenge"]
            .nunique()
        )
        checkout_summary.name = "Check-out quiz correct"

        summary = (
            baseline_summary
            .join(post_confidence_summary, how="outer")
            .join(checkout_summary, how="outer")
        )
        summary["Check-out quiz correct"] = summary.get("Check-out quiz correct", 0)
        summary["Check-out quiz correct"] = summary["Check-out quiz correct"].fillna(0)
        if "Baseline confidence" in summary and "Check-out confidence" in summary:
            summary["Confidence change"] = summary["Check-out confidence"] - summary["Baseline confidence"]
        for column in ("Baseline confidence", "Check-out confidence", "Confidence change"):
            if column in summary:
                summary[column] = summary[column].round(1)
        st.dataframe(summary.reset_index(), hide_index=True, width="stretch")

    st.stop()

pid = st.session_state.pid
xp = total_xp(pid)
badge = badge_for_xp(xp)
board = leaderboard()
rank = "—"
if not board.empty:
    pid_list = board["PID"].tolist()
    if pid in pid_list:
        rank = int(board["Rank"].tolist()[pid_list.index(pid)])

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown(f"## 🙋 {st.session_state.first_name} {st.session_state.last_name}")
    st.metric("XP", f"{xp}/{PERFECT_SCORE}")
    st.metric("Badge", badge.split(" ",1)[0], badge.split(" ",1)[1] if " " in badge else "", delta_color="off")
    st.metric("Progress", f"{boss_defeated_percent(xp)}%")
    st.metric("Class Rank", f"#{rank}" if rank != "—" else "—")

    enforce_page_access(pid)  # may correct/rerun before the widget below is instantiated

    selected = st.radio(
        "Game map",
        PAGE_OPTIONS,
        key="selected_page",
    )

    st.divider()
    if st.button("Log out"):
        log_out_student()
        st.rerun()

# -----------------------------
# Header
# -----------------------------
if st.session_state.last_selected_page != selected:
    st.iframe(
        f"""
        <script>
        const token = {json.dumps(selected)};
        function scrollStatsQuestToTop() {{
            const win = window.parent;
            const doc = win.document;
            const selectors = [
                '[data-testid="stAppViewContainer"]',
                '[data-testid="stMain"]',
                'section.main',
                '.main',
                'body',
                'html'
            ];

            try {{
                win.scrollTo({{ top: 0, left: 0, behavior: "auto" }});
            }} catch (error) {{}}

            selectors.forEach((selector) => {{
                const element = doc.querySelector(selector);
                if (!element) return;
                try {{
                    element.scrollTop = 0;
                    element.scrollLeft = 0;
                    if (element.scrollTo) {{
                        element.scrollTo({{ top: 0, left: 0, behavior: "auto" }});
                    }}
                }} catch (error) {{}}
            }});
        }}

        scrollStatsQuestToTop();
        const requestFrame = window.parent.requestAnimationFrame || window.requestAnimationFrame;
        if (requestFrame) {{
            requestFrame(scrollStatsQuestToTop);
        }}
        [50, 150, 350, 700, 1200, 2500].forEach((delay) => {{
            window.setTimeout(scrollStatsQuestToTop, delay);
        }});
        </script>
        """,
        height=1,
    )
    st.session_state.last_selected_page = selected

st.markdown(
    f"""
    <div class="mobile-topbar">
        <div class="mobile-topbar-title">{selected}</div>
        <div class="mobile-topbar-meta">🎮 StatsQuest · {xp}/{PERFECT_SCORE} XP · {badge}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="game-title">🎮 StatsQuest: Modeling & Simulation</div>', unsafe_allow_html=True)
st.caption("Short statistics challenges with XP, progress, and a leaderboard.")

page_ctx = SimpleNamespace(
    pid=pid,
    xp=xp,
    PERFECT_SCORE=PERFECT_SCORE,
    STORY=STORY,
    content_get=content_get,
    show_youtube_resources=show_youtube_resources,
    show_level_progress=show_level_progress,
    show_level_1_formulas=show_level_1_formulas,
    show_level_2_formulas=show_level_2_formulas,
    show_level_4_formulas=show_level_4_formulas,
    show_distribution_reference=show_distribution_reference,
    show_descriptive_stats=show_descriptive_stats,
    show_challenge_acknowledgement=show_challenge_acknowledgement,
    show_challenge_status_box=show_challenge_status_box,
    show_optional_hint=show_optional_hint,
    show_boss_progress=show_boss_progress,
    answer_radio=answer_radio,
    score_answer=score_answer,
    record_completion_once=record_completion_once,
    bonus_unlocked=bonus_unlocked,
    correct_challenges=correct_challenges,
    is_stage_complete=is_stage_complete,
    show_step_header=show_step_header,
    show_scenario_card=show_scenario_card,
    show_record_status=show_record_status,
    prominent_control_label=prominent_control_label,
    show_video_acknowledgement=show_video_acknowledgement,
    show_next_button=show_next_button,
)

# -----------------------------
# Pre-assessment (Starting Check-In)
# -----------------------------
if selected == "🧭 Starting Check-In":
    st.header("🧭 Starting Check-In")
    st.markdown(STORY["pre_assessment"])

    if self_assessment_complete(pid, "pre"):
        avg_confidence, answered_count, total_count = self_assessment_summary(pid, "pre")
        if avg_confidence is None:
            st.success("Baseline recorded.")
        else:
            st.success(f"Baseline recorded: average confidence {avg_confidence:.1f}/5 across {answered_count}/{total_count} topics.")
        st.caption("This didn't affect your XP — it just gives us something to compare against once you finish.")
        show_confidence_review(pid, "pre")
    else:
        st.info(
            "Rate your confidence before Level 1. There are no right or wrong answers. This does not affect XP."
        )
        with st.form("pre_assessment_form"):
            st.write(f"**{confidence_prompt('pre')}**")
            pre_answers = {}
            for key, prompt in confidence_items("pre"):
                pre_answers[key] = st.radio(prompt, confidence_scale_options("pre"), key=f"pre_{key}", index=None)
            pre_submitted = st.form_submit_button("Submit self-assessment", type="primary")
        if pre_submitted:
            if any(value is None for value in pre_answers.values()):
                st.warning("Rate all 5 topics before submitting.")
            else:
                for key in CONFIDENCE_TOPIC_KEYS:
                    record_confidence_rating(pid, "pre", key, pre_answers[key])
                set_answer_feedback("success", "Self-assessment recorded. You can start Level 1.")
                st.rerun()
    show_next_button()

# -----------------------------
# Home / map
# -----------------------------
elif selected == "🏠 Home":
    st.header("🗺️ Game Map")
    st.markdown(STORY["intro"])
    show_how_to_play()
    show_youtube_resources("home")
    show_formula_reference()

    for level, info in LEVELS.items():
        accessible = page_accessible(pid, next(page for page, page_level in PAGE_LEVELS.items() if page_level == level))
        complete = level_complete(pid, level)
        answered, total, _ = level_progress(pid, level)
        if complete:
            status = "✅ Complete"
        elif accessible:
            status = "🟢 Available"
        else:
            status = "🔒 Locked until earlier questions are correct"
        earned = level_score(pid, level)
        st.markdown(
            f"""
            <div class="level-card">
                <b>{info['icon']} Level {level}: {info['name']}</b><br>
                <span class="small-muted">{status} · Required steps: {answered}/{total} · XP earned here: {earned}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.subheader("Mission")
    st.write(content_get("home.mission", "Complete five challenges and help the simulation team understand what the data is telling them."))
    goal_setting = content_get("assessment.goal_setting", {})
    goal_options = goal_setting.get("options", []) if isinstance(goal_setting, dict) else []
    if goal_options:
        st.subheader("Your Goal")
        selected_goal = st.radio(
            goal_setting.get("prompt", "What would you most like to get better at today?"),
            goal_options,
            index=None,
            key="learning_goal_choice",
        )
        if selected_goal:
            st.session_state.learning_goal = selected_goal
            record_completion_once(pid, 0, "SRL_GOAL", selected_goal)
            st.caption(f"Your goal: {selected_goal}")
    if self_assessment_complete(pid, "pre"):
        avg_confidence, _, _ = self_assessment_summary(pid, "pre")
        if avg_confidence is None:
            st.caption("📈 Baseline self-assessment recorded.")
        else:
            st.caption(f"📈 Baseline confidence: {avg_confidence:.1f}/5 before training.")

    st.subheader("Badges")
    badge_df = pd.DataFrame(
        BADGE_DESCRIPTIONS,
        columns=["Badge", "Score needed", "What it means"],
    )
    st.dataframe(badge_df, hide_index=True, width="stretch")
    show_next_button()

# -----------------------------
# Level 1
# -----------------------------
elif selected == PAGE_OPTIONS[2]:
    render_level_1(page_ctx)

# -----------------------------
# Level 2
# -----------------------------
elif selected == PAGE_OPTIONS[3]:
    render_level_2(page_ctx)

# -----------------------------
# Level 3
# -----------------------------
elif selected == PAGE_OPTIONS[4]:
    render_level_3(page_ctx)

# -----------------------------
# Level 4
# -----------------------------
elif selected == PAGE_OPTIONS[5]:
    render_level_4(page_ctx)

# -----------------------------
# Level 5
# -----------------------------
elif selected == PAGE_OPTIONS[6]:
    render_level_5(page_ctx)

# -----------------------------
# Post-assessment (Final Check-Out)
# -----------------------------
elif selected == "📊 Final Check-Out":
    st.header("📊 Final Check-Out")
    st.markdown(STORY["post_assessment"])

    quiz_done = assessment_complete(pid, "post")
    confidence_done = self_assessment_complete(pid, "post")

    if quiz_done:
        post_correct, post_total = assessment_score(pid, "post")
        st.success(f"Check-out quiz recorded: {post_correct}/{post_total} correct.")
        show_assessment_review(pid, "post")
    else:
        st.info(
            "Five questions. No XP effect."
        )
        with st.form("post_assessment_form"):
            post_answers = {}
            for key, prompt, options, _ in ASSESSMENT_QUESTIONS:
                post_answers[key] = answer_radio(prompt, options, key=f"post_{key}", index=None)
            post_submitted = st.form_submit_button("Submit check-out", type="primary")
        if post_submitted:
            if any(value is None for value in post_answers.values()):
                st.warning("Answer all 5 questions before submitting.")
            else:
                for key, _, _, correct_answer in ASSESSMENT_QUESTIONS:
                    record_diagnostic_answer(pid, "post", key, post_answers[key], post_answers[key] == correct_answer)
                set_answer_feedback("success", "Check-out quiz recorded. Now rate your confidence again below.")
                st.rerun()

    # The confidence re-rating only appears once the quiz is done, and is a
    # separate step from it -- it's what actually lets us show a rise (or
    # not) in confidence, which the quiz alone can't answer.
    if quiz_done:
        st.divider()
        if confidence_done:
            st.subheader("Confidence: before vs. after")
            show_confidence_change(pid)
            show_confidence_review(pid, "post")
        else:
            st.subheader("Rate your confidence again")
            st.info(
                "Same five topics as your baseline check-in. This shows how much changed "
                "for you — it doesn't affect your XP."
            )
            with st.form("post_confidence_form"):
                st.write(f"**{confidence_prompt('post')}**")
                post_confidence_answers = {}
                for key, prompt in confidence_items("post"):
                    post_confidence_answers[key] = st.radio(prompt, confidence_scale_options("post"), key=f"postself_{key}", index=None)
                confidence_submitted = st.form_submit_button("Submit confidence rating", type="primary")
            if confidence_submitted:
                if any(value is None for value in post_confidence_answers.values()):
                    st.warning("Rate all 5 topics before submitting.")
                else:
                    for key in CONFIDENCE_TOPIC_KEYS:
                        record_confidence_rating(pid, "post", key, post_confidence_answers[key])
                    set_answer_feedback("success", "Confidence rating recorded. Here's how far you've come.")
                    st.rerun()

    show_next_button()

# -----------------------------
# Leaderboard
# -----------------------------
elif selected == "🥇 Leaderboard":
    st.header("🥇 Class Leaderboard")
    board = leaderboard()
    if board.empty:
        st.info("No scores yet.")
    else:
        st.dataframe(board.drop(columns=["PID"]), hide_index=True, width="stretch")
        top = board.iloc[0]
        st.success(f"Current leader: {top['Name']} with {int(top['XP'])} XP")

    st.subheader("Your attempt history")
    history = participant_stats(pid)
    if history.empty:
        st.info("No scored attempts yet.")
    else:
        st.dataframe(
            history[["level","challenge","correct","points","created_at"]],
            hide_index=True,
            width="stretch"
        )
    show_next_button()
    st.success("You have reached the end of StatsQuest.")
    st.info("Score screenshot: before exiting, save a screenshot of your final score on this page and share it with your TA or professor.")
    if st.button("Exit application", type="primary", width="stretch"):
        log_out_student()
        st.rerun()
