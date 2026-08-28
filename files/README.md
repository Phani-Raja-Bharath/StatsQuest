# StatsQuest — Streamlit Statistics Game

An individual, self-paced Streamlit game for **Statistics for Modeling & Simulation**. Students
set a personal goal, rate their confidence, play five levels with predict → experiment →
observe → explain scaffolding that fades as they progress, then check out with a knowledge quiz
and a second confidence rating — so both the student and the instructor can see what actually
changed.

## Game structure

1. **🎯 Meanhaven Station** — mean, median, mode; predicting and observing the effect of an
   outlier; transferring the idea to a new scenario.
2. **📏 Spreadmoor Yards** — range, variance, standard deviation; two datasets with the same mean
   but different spread.
3. **🎲 Distribution Junction** — matching Normal, Uniform, Bernoulli, and Binomial to real
   scenarios, with optional on-request hints.
4. **✈️ Arrivals Terminal** — Poisson for counts, Exponential for wait times.
5. **🏆 Simulation Lab** — Monte Carlo simulation of airport security workload; how estimates
   stabilize as the number of runs increases.

Scaffolding fades level by level: Level 1 is fully guided (prediction + observation required
before answering), Level 3 offers hints only on request, Level 5 is independent — see
`content.json`'s `self_regulation.scaffold_fading` for the exact wording shown to students.

## Gaming features

- Individual login (first name + last name + a self-chosen 4-digit PIN)
- Personal learning goal, set before the diagnostic check-in
- Pre-course confidence self-rating (5 topics, 1–5 scale) and a matching post-course
  re-rating, so the check-out shows an actual **confidence change** (not just a quiz score)
- XP scoring, level unlocking, badges, progression map, leaderboard, instant feedback
- Two attempts per required question: a wrong first try gets one retry; a correct second try
  earns half-credit XP; a second wrong try reveals the correct answer and locks the challenge
  at 0 XP (the student keeps answering until correct so the next page opens)
- One bonus "make-up XP" challenge per level, worth the same XP as a regular challenge in that
  level, so a participant who lost XP to a retry can earn it back before the next level unlocks
- Post-course quiz uses different scenarios than the training levels (transfer, not recall)
- SQLite locally, Postgres (Neon) in production — same code path either way
- Password-protected Admin Dashboard: full leaderboard, full attempt log, confidence-change
  summary, participant completion status, reset/delete controls, all with CSV export
- Light theme by default via `.streamlit/config.toml`

## Project structure

```
app.py                 Entry point: session/login, sidebar, navigation, admin dashboard,
                        Home / Diagnostic Check-In / Mastery Check-Out pages
content_loader.py       Loads and looks up content.json
db.py                   SQLite/Postgres connection handling and all queries
navigation.py           Page order and page-name constants
scoring.py              XP, badges, challenge tables
.streamlit/config.toml  Streamlit config; defaults the app to light theme
level_pages/level_N.py  One module per level's page content
content.json            All student-facing copy: story text, level prompts, formulas,
                        video links, hints, and the self-regulation/goal-setting text —
                        edit this to change wording without touching app.py
```

Every string pulled from `content.json` has a matching fallback baked into the Python code, so a
missing or invalid `content.json` degrades gracefully instead of breaking the app (the Admin
Dashboard shows a warning if that happens).

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

or:

```bash
python -m streamlit run app.py
```

## Individual login

This is an **individual** challenge, not team-based. On first entry, each person types their
first name, last name, and picks their own 4-digit PIN. That name + PIN combination is their
login — using the exact same name and PIN again resumes their progress. The PIN exists so two
participants who happen to share a name don't collide into the same record, and so no one else
can casually view or answer for someone else.

If someone forgets their PIN, open the Admin Dashboard's **👤 Participants** section and search
by name — it lists every registered participant's PIN directly (that section is admin-only, and
the PIN is never shown to other students).

## Admin Dashboard — checking scores

On the login screen, expand **"🛠️ Instructor / Admin access"** and enter the admin password to
reach the dashboard directly (no participant login needed). It shows:
- The full leaderboard (every participant, rank, XP, correct count, attempts) with CSV export
- The full attempt log (every answer, correct/incorrect, points, timestamp) with CSV export
- A completion-status table showing each participant's XP and which stage of each level is
  complete, with CSV export
- A confidence summary: baseline confidence, check-out confidence, the change between them, and
  check-out quiz score, per participant
- Participant management controls:
  - **Reset scoring** keeps the participant's name/PIN but deletes attempts, XP, baseline,
    check-out, and progress so they can start again with the same login.
  - **Delete participant** removes the participant record and all attempt history. The student
    must register again from scratch.

**The admin password must be set as a secret — there is no built-in default.** Without it, the
"Instructor / Admin access" panel shows a notice that admin access is disabled instead of
falling back to a guessable password:

```bash
# macOS/Linux
export STATSQUEST_ADMIN_PASSWORD="your-password-here"
streamlit run app.py
```

```powershell
# Windows PowerShell
$env:STATSQUEST_ADMIN_PASSWORD = "your-password-here"
streamlit run app.py
```

Or set it in `.streamlit/secrets.toml` (see below) — that's the usual way for a persistent local
setup or a Streamlit Cloud deployment. **Never put the real password in this README, in
`content.json`, or anywhere else that gets committed to git** — it only belongs in
`.streamlit/secrets.toml` (git-ignored) or your deployment platform's secrets manager. If you
need a private, non-committed place to jot down the actual password and access steps for
yourself, see "Keeping your own private notes" below.

Scores persist in the database for as long as it exists, so you can reopen the Admin Dashboard
at any time after the session — even after restarting the app — to review results.

Reset and delete actions require typing `RESET` or `DELETE` before clicking the button. This is
intentional: both actions remove scoring/progress data, and the confirmation prevents accidental
clicks during class. If a participant is deleted while their browser is still open, the app checks
the database on the next rerun/refresh, clears that browser's old Streamlit session state, and
sends them back to registration.

## Deploying with Neon Postgres

For Streamlit Cloud, use Neon Postgres instead of local SQLite so scores persist after app
restarts and redeploys.

1. Create a free Neon project.
2. Copy the Neon pooled connection string.
3. In Streamlit Cloud, open the app settings and add this secret:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require"
STATSQUEST_ADMIN_PASSWORD = "your-password-here"
```

The app automatically uses Neon when `DATABASE_URL` or `NEON_DATABASE_URL` is available.
Without either secret, it falls back to the local `stats_game.db` file.

For local development, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
and paste your real Neon connection string there. The real secrets file is ignored by git.
Keep using `DATABASE_URL` or `NEON_DATABASE_URL` for the database connection; `NEON_API_KEY`
is included only as a safe placeholder if you need to store that key locally later.

## Keeping your own private notes

If you want a personal cheat-sheet with the real admin password, database access steps, and
similar operational details, keep it in a file that is **not committed to git** — name it
something like `ADMIN_ACCESS.local.md` in this folder. This repo's `.gitignore` already excludes
that exact filename so it's safe to create locally without risking an accidental commit; check
`git status` before committing regardless, since a rename or a different filename won't be
covered by that rule.

## Classroom suggestion

Give participants 20–30 minutes to work individually.

Suggested format:
- Project the leaderboard periodically (names only; no answer details are shown there)
- Debrief as a class by asking a few participants to explain an answer they had to retry
- Compare the class's average confidence change in the Admin Dashboard against how the quiz
  scores actually landed — a topic with a big confidence rise but a low quiz score is worth
  revisiting

The database is created automatically. Use the Admin Dashboard's reset/delete controls for
individual students. Connect to the database directly only if you need to clear the entire class
before a new session.
