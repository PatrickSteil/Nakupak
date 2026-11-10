"""Plain-text ingredient parsing and category suggestion (no LLM)."""
import re

_VULGAR = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125}
_V = "".join(_VULGAR)

_QTY_RE = re.compile(
    rf"""^\s*(?:
        (?P<whole>\d+)\s*(?P<vfrac>[{_V}])
        |(?P<w2>\d+)\s+(?P<num>\d+)/(?P<den>\d+)
        |(?P<n2>\d+)/(?P<d2>\d+)
        |(?P<only>[{_V}])
        |(?P<dec>\d+(?:[.,]\d+)?)(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?
    )""",
    re.X,
)

# unit word -> (app unit, multiplier)
_UNITS = {
    "g": ("g", 1), "gr": ("g", 1), "gramm": ("g", 1), "mg": ("g", 0.001),
    "kg": ("kg", 1), "kilo": ("kg", 1),
    "ml": ("ml", 1), "cl": ("ml", 10), "dl": ("ml", 100),
    "l": ("l", 1), "liter": ("l", 1), "litre": ("l", 1),
    "x": ("x", 1), "stk": ("x", 1), "stück": ("x", 1), "stueck": ("x", 1),
    "pcs": ("x", 1), "pc": ("x", 1),
}
_UNIT_RE = re.compile(
    r"^\s*(?P<u>" + "|".join(sorted(map(re.escape, _UNITS), key=len, reverse=True)) + r")\.?(?=\s|$)",
    re.I,
)

MAX_LINES = 200
MAX_LINE_LENGTH = 200


def _quantity(m: re.Match) -> float:
    if m.group("whole"):
        return int(m.group("whole")) + _VULGAR[m.group("vfrac")]
    if m.group("w2"):
        return int(m.group("w2")) + int(m.group("num")) / int(m.group("den"))
    if m.group("n2"):
        return int(m.group("n2")) / int(m.group("d2")) if int(m.group("d2")) else 1
    if m.group("only"):
        return _VULGAR[m.group("only")]
    return float(m.group("dec").replace(",", "."))


def parse_ingredient_line(line: str) -> dict | None:
    """'2 l Milch' -> {'name': 'Milch', 'quantity': 2.0, 'unit': 'l'}; None for blank/headers."""
    line = line.strip()[:MAX_LINE_LENGTH]
    line = re.sub(r"^[\-•–·*]+\s*", "", line)  # bullets
    if not line or line.endswith(":"):
        return None

    quantity, unit, rest = 1.0, "x", line
    m = _QTY_RE.match(line)
    if m:
        quantity = _quantity(m)
        rest = line[m.end():]
        um = _UNIT_RE.match(rest)
        if um:
            unit, factor = _UNITS[um.group("u").lower()]
            quantity *= factor
            rest = rest[um.end():]

    rest = re.sub(r"\([^)]*\)", "", rest)  # "(optional)"
    rest = rest.split(",")[0]  # "Zwiebeln, gewürfelt" -> "Zwiebeln"
    name = re.sub(r"\s+", " ", rest).strip(" .;-–")
    if not name:
        return None
    name = name[0].upper() + name[1:]
    return {"name": name, "quantity": round(quantity, 3) or 1.0, "unit": unit}


def parse_ingredients(text: str) -> list[dict]:
    """One ingredient per line; duplicate names are dropped (first wins)."""
    seen, result = set(), []
    for line in text.splitlines()[:MAX_LINES]:
        parsed = parse_ingredient_line(line)
        if parsed and parsed["name"].lower() not in seen:
            seen.add(parsed["name"].lower())
            result.append(parsed)
    return result


def suggest_category_id(name: str, items) -> int | None:
    """Most common category among existing items whose name overlaps `name`.

    `items` are Item rows (with name and category_id). German compounds count:
    'Vollmilch' matches an existing 'Milch'.
    """
    needle = name.strip().lower()
    if len(needle) < 3:
        return None
    counts: dict[int, int] = {}
    for it in items:
        if it.category_id is None:
            continue
        other = it.name.strip().lower()
        if len(other) < 3 or other == needle:
            if other == needle:
                counts[it.category_id] = counts.get(it.category_id, 0) + 1
            continue
        if other in needle or needle in other:
            counts[it.category_id] = counts.get(it.category_id, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)
