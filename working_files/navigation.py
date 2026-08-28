PAGE_LEVELS = {
    "🎯 Level 1 — The Unusual Commute": 1,
    "📏 Level 2 — Same Average, Different Machines": 2,
    "🎲 Level 3 — Choose the Right Randomness": 3,
    "✈️ Level 4 — Airport Arrival Lab": 4,
    "🏆 Level 5 — The Simulation Decision": 5,
}

PAGE_OPTIONS = [
    "🏠 Home",
    "🧭 Starting Check-In",
    "🎯 Level 1 — The Unusual Commute",
    "📏 Level 2 — Same Average, Different Machines",
    "🎲 Level 3 — Choose the Right Randomness",
    "✈️ Level 4 — Airport Arrival Lab",
    "🏆 Level 5 — The Simulation Decision",
    "📊 Final Check-Out",
    "🥇 Leaderboard",
]


def page_index(page: str) -> int:
    return PAGE_OPTIONS.index(page) if page in PAGE_OPTIONS else 0


def next_page(page: str) -> str | None:
    index = page_index(page)
    if index >= len(PAGE_OPTIONS) - 1:
        return None
    return PAGE_OPTIONS[index + 1]


def previous_page(page: str) -> str | None:
    index = page_index(page)
    if index <= 0:
        return None
    return PAGE_OPTIONS[index - 1]
