MAX_WRONG_ATTEMPTS = 2
CONSOLATION_FRACTION = 0.5

LEVELS = {
    1: {"name": "The Unusual Commute", "icon": "🎯"},
    2: {"name": "Same Average, Different Machines", "icon": "📏"},
    3: {"name": "Choose the Right Randomness", "icon": "🎲"},
    4: {"name": "Airport Arrival Lab", "icon": "✈️"},
    5: {"name": "The Simulation Decision", "icon": "🏆"},
}

LEVEL_MAX_POINTS = {
    1: 75,
    2: 90,
    3: 80,
    4: 105,
    5: 135,
}
PERFECT_SCORE = sum(LEVEL_MAX_POINTS.values())

# Every level follows the same instructional sequence -- Watch, Explore, Try,
# Apply, then an optional Bonus make-up question -- rather than levels
# themselves being progressively less scaffolded. Watch is 0 XP (it is an
# acknowledgement, not a graded step); Explore/Try/Apply are weighted equally
# within a level for simplicity (the spec permits either equal or
# differentiated weights; equal was chosen here).
LEVEL_CHALLENGES = {
    1: ["L1_VIDEO_ACK", "L1_PREDICT", "L1_OBSERVE", "L1_OUTLIER", "L1_CENTER", "L1_APPLY", "L1_REFLECT", "L1_BONUS"],
    2: ["L2_VIDEO_ACK", "L2_CONSISTENCY", "L2_PREDICT_SD", "L2_SD", "L2_APPLY", "L2_BONUS"],
    3: ["L3_VIDEO_ACK", "L3_Q1", "L3_Q2", "L3_Q3", "L3_Q4", "L3_BONUS"],
    4: ["L4_VIDEO_ACK", "L4_PREDICT", "L4_OBSERVE", "L4_POISSON", "L4_EXP", "L4_APPLY", "L4_BONUS"],
    5: ["L5_VIDEO_ACK", "L5_PREDICT", "L5_OBSERVE", "L5_STABILITY", "L5_PURPOSE", "L5_APPLY", "L5_BONUS"],
}

LEVEL_REQUIRED_CHALLENGES = {
    level: [challenge for challenge in challenges if not challenge.endswith("_BONUS")]
    for level, challenges in LEVEL_CHALLENGES.items()
}

CHALLENGE_POINTS = {
    "L1_OUTLIER": 25,
    "L1_CENTER": 25,
    "L1_APPLY": 25,
    "L1_BONUS": 25,
    "L2_CONSISTENCY": 30,
    "L2_SD": 30,
    "L2_APPLY": 30,
    "L2_BONUS": 30,
    "L3_Q1": 20,
    "L3_Q2": 20,
    "L3_Q3": 20,
    "L3_Q4": 20,
    "L3_BONUS": 20,
    "L4_POISSON": 35,
    "L4_EXP": 35,
    "L4_APPLY": 35,
    "L4_BONUS": 35,
    "L5_STABILITY": 45,
    "L5_PURPOSE": 45,
    "L5_APPLY": 45,
    "L5_BONUS": 45,
}

# Kept identical to the plain labels shown on each level's own page (just
# "Question 1", "Prediction", "Bonus Question", ...) rather than separate
# flavor names -- these strings appear in the progress bar's "Completed" /
# "Pending" captions, and having them not match what's on the page is
# itself a source of confusion.
CHALLENGE_NAMES = {
    "SRL_GOAL": "Personal Goal",
    "L1_VIDEO_ACK": "Watch",
    "L1_PREDICT": "Prediction",
    "L1_OBSERVE": "Observation",
    "L1_OUTLIER": "Explore",
    "L1_CENTER": "Try",
    "L1_APPLY": "Apply",
    "L1_REFLECT": "Reflection",
    "L1_BONUS": "Bonus Question",
    "L2_VIDEO_ACK": "Watch",
    "L2_CONSISTENCY": "Explore",
    "L2_PREDICT_SD": "Prediction",
    "L2_SD": "Try",
    "L2_APPLY": "Apply",
    "L2_BONUS": "Bonus Question",
    "L3_VIDEO_ACK": "Watch",
    "L3_Q1": "Explore",
    "L3_Q2": "Try",
    "L3_Q3": "Apply",
    "L3_Q4": "Apply",
    "L3_BONUS": "Bonus Question",
    "L4_VIDEO_ACK": "Watch",
    "L4_PREDICT": "Prediction",
    "L4_OBSERVE": "Observation",
    "L4_POISSON": "Explore",
    "L4_EXP": "Try",
    "L4_APPLY": "Apply",
    "L4_BONUS": "Bonus Question",
    "L5_VIDEO_ACK": "Watch",
    "L5_PREDICT": "Prediction",
    "L5_OBSERVE": "Observation",
    "L5_STABILITY": "Explore",
    "L5_PURPOSE": "Try",
    "L5_APPLY": "Apply",
    "L5_BONUS": "Bonus Question",
}

# Structured metadata for every scored/tracked activity: level, concept,
# instructional stage, whether it's required to advance, and its scaffold
# tier. This is what lets the admin dashboard (or later analysis) report by
# stage/scaffold without inferring meaning from challenge-id strings.
# scaffold: "none" (video ack / self-report, not a graded question),
# "high" (Explore), "reduced" (Try), "minimal" (Apply), "optional" (bonus).
CHALLENGE_META = {
    "SRL_GOAL":     {"level": 0, "concept": "goal_setting", "stage": None,      "required": True,  "scaffold": "none"},
    "L1_VIDEO_ACK": {"level": 1, "concept": "center",       "stage": "watch",   "required": True,  "scaffold": "none"},
    "L1_PREDICT":   {"level": 1, "concept": "center",       "stage": "explore", "required": True,  "scaffold": "none"},
    "L1_OBSERVE":   {"level": 1, "concept": "center",       "stage": "explore", "required": True,  "scaffold": "none"},
    "L1_OUTLIER":   {"level": 1, "concept": "center",       "stage": "explore", "required": True,  "scaffold": "high"},
    "L1_CENTER":    {"level": 1, "concept": "center",       "stage": "try",     "required": True,  "scaffold": "reduced"},
    "L1_APPLY":     {"level": 1, "concept": "center",       "stage": "apply",   "required": True,  "scaffold": "minimal"},
    "L1_REFLECT":   {"level": 1, "concept": "center",       "stage": "complete", "required": True, "scaffold": "none"},
    "L1_BONUS":     {"level": 1, "concept": "center",       "stage": None,      "required": False, "scaffold": "optional"},

    "L2_VIDEO_ACK":   {"level": 2, "concept": "spread", "stage": "watch",   "required": True,  "scaffold": "none"},
    "L2_CONSISTENCY": {"level": 2, "concept": "spread", "stage": "explore", "required": True,  "scaffold": "high"},
    "L2_PREDICT_SD":  {"level": 2, "concept": "spread", "stage": "try",     "required": True,  "scaffold": "none"},
    "L2_SD":          {"level": 2, "concept": "spread", "stage": "try",     "required": True,  "scaffold": "reduced"},
    "L2_APPLY":       {"level": 2, "concept": "spread", "stage": "apply",   "required": True,  "scaffold": "minimal"},
    "L2_BONUS":       {"level": 2, "concept": "spread", "stage": None,      "required": False, "scaffold": "optional"},

    "L3_VIDEO_ACK": {"level": 3, "concept": "distributions", "stage": "watch",   "required": True,  "scaffold": "none"},
    "L3_Q1":        {"level": 3, "concept": "distributions", "stage": "explore", "required": True,  "scaffold": "high"},
    "L3_Q2":        {"level": 3, "concept": "distributions", "stage": "try",     "required": True,  "scaffold": "reduced"},
    "L3_Q3":        {"level": 3, "concept": "distributions", "stage": "apply",   "required": True,  "scaffold": "minimal"},
    "L3_Q4":        {"level": 3, "concept": "distributions", "stage": "apply",   "required": True,  "scaffold": "minimal"},
    "L3_BONUS":     {"level": 3, "concept": "distributions", "stage": None,      "required": False, "scaffold": "optional"},

    "L4_VIDEO_ACK": {"level": 4, "concept": "arrivals", "stage": "watch",   "required": True,  "scaffold": "none"},
    "L4_PREDICT":   {"level": 4, "concept": "arrivals", "stage": "explore", "required": True,  "scaffold": "none"},
    "L4_OBSERVE":   {"level": 4, "concept": "arrivals", "stage": "explore", "required": True,  "scaffold": "none"},
    "L4_POISSON":   {"level": 4, "concept": "arrivals", "stage": "explore", "required": True,  "scaffold": "high"},
    "L4_EXP":       {"level": 4, "concept": "arrivals", "stage": "try",     "required": True,  "scaffold": "reduced"},
    "L4_APPLY":     {"level": 4, "concept": "arrivals", "stage": "apply",   "required": True,  "scaffold": "minimal"},
    "L4_BONUS":     {"level": 4, "concept": "arrivals", "stage": None,      "required": False, "scaffold": "optional"},

    "L5_VIDEO_ACK":  {"level": 5, "concept": "monte_carlo", "stage": "watch",   "required": True,  "scaffold": "none"},
    "L5_PREDICT":    {"level": 5, "concept": "monte_carlo", "stage": "explore", "required": True,  "scaffold": "none"},
    "L5_OBSERVE":    {"level": 5, "concept": "monte_carlo", "stage": "explore", "required": True,  "scaffold": "none"},
    "L5_STABILITY":  {"level": 5, "concept": "monte_carlo", "stage": "explore", "required": True,  "scaffold": "high"},
    "L5_PURPOSE":    {"level": 5, "concept": "monte_carlo", "stage": "try",     "required": True,  "scaffold": "reduced"},
    "L5_APPLY":      {"level": 5, "concept": "monte_carlo", "stage": "apply",   "required": True,  "scaffold": "minimal"},
    "L5_BONUS":      {"level": 5, "concept": "monte_carlo", "stage": None,      "required": False, "scaffold": "optional"},
}

BADGE_DESCRIPTIONS = [
    ("🎒 Rookie Modeler", "0-49 XP", "Getting started."),
    ("⭐ Stats Explorer", "50-109 XP", "Understands mean, median, mode, and range."),
    ("🥉 Variability Scout", "110-179 XP", "Can compare standard deviation and distributions."),
    ("🥈 Distribution Strategist", "180-249 XP", "Can match distributions to situations."),
    ("🥇 Monte Carlo Master", f"250-{PERFECT_SCORE - 1} XP", "Can reason about simulation results."),
    ("👑 Simulation Champion", f"{PERFECT_SCORE} XP", "Perfect score. All challenges complete."),
]


def badge_for_xp(xp: int) -> str:
    if xp >= PERFECT_SCORE:
        return "👑 Simulation Champion"
    if xp >= 250:
        return "🥇 Monte Carlo Master"
    if xp >= 180:
        return "🥈 Distribution Strategist"
    if xp >= 110:
        return "🥉 Variability Scout"
    if xp >= 50:
        return "⭐ Stats Explorer"
    return "🎒 Rookie Modeler"


def boss_defeated_percent(xp: int) -> float:
    return min(100, round((xp / PERFECT_SCORE) * 100, 1))


def challenge_label(challenge: str) -> str:
    return CHALLENGE_NAMES.get(challenge, challenge)


def challenge_labels(challenges: list[str] | set[str] | tuple[str, ...]) -> str:
    return ", ".join(challenge_label(challenge) for challenge in challenges)
