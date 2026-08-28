import json
from typing import Any


REQUIRED_CONTENT_KEYS = ("story", "home", "assessment", "videos", "formulas", "level_copy")


def load_content(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as content_file:
            content = json.load(content_file)
    except Exception:
        return {}
    return content if isinstance(content, dict) else {}


def missing_required_keys(content: dict[str, Any]) -> list[str]:
    return [key for key in REQUIRED_CONTENT_KEYS if key not in content]


def get_content(content: dict[str, Any], path: str, default: Any = "") -> Any:
    current: Any = content
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def split_markdown_title(markdown_text: str, default_title: str) -> tuple[str, str]:
    title, separator, body = str(markdown_text).partition("\n\n")
    title = title.lstrip("#").strip()  # "### Heading" -> "Heading" for st.subheader()
    if not separator:
        return default_title, str(markdown_text)
    return title or default_title, body
