import pytest

from app.ingredients import parse_ingredient_line, parse_ingredients


@pytest.mark.parametrize("line,expected", [
    ("2 l Milch", ("Milch", 2, "l")),
    ("300g Mehl", ("Mehl", 300, "g")),
    ("300 g Mehl", ("Mehl", 300, "g")),
    ("3 Eier", ("Eier", 3, "x")),
    ("Salz", ("Salz", 1, "x")),
    ("1,5 kg Kartoffeln", ("Kartoffeln", 1.5, "kg")),
    ("1.5 kg Kartoffeln", ("Kartoffeln", 1.5, "kg")),
    ("1/2 Zwiebel", ("Zwiebel", 0.5, "x")),
    ("½ Zwiebel", ("Zwiebel", 0.5, "x")),
    ("1 1/2 l Wasser", ("Wasser", 1.5, "l")),
    ("1½ kg Mehl", ("Mehl", 1.5, "kg")),
    ("2-3 Karotten", ("Karotten", 2, "x")),
    ("5 dl Sahne", ("Sahne", 500, "ml")),
    ("2 cl Rum", ("Rum", 20, "ml")),
    ("2 Stk. Paprika", ("Paprika", 2, "x")),
    ("2x Tomaten", ("Tomaten", 2, "x")),
    ("- 200 g Butter", ("Butter", 200, "g")),
    ("• 200 g Butter", ("Butter", 200, "g")),
    ("2 Zwiebeln, gewürfelt", ("Zwiebeln", 2, "x")),
    ("1 Prise Salz (optional)", ("Prise Salz", 1, "x")),
    ("milch", ("Milch", 1, "x")),
    ("2 Lauch", ("Lauch", 2, "x")),  # 'l' is not the unit in 'Lauch'
    ("3 Gurken", ("Gurken", 3, "x")),  # 'g' is not the unit in 'Gurken'
    ("2 EL Olivenöl", ("Olivenöl", 2, "el")),
    ("1 TL Salz", ("Salz", 1, "tl")),
    ("1,5 EL. Zitronensaft", ("Zitronensaft", 1.5, "el")),
    ("½ TL Pfeffer, gemahlen", ("Pfeffer", 0.5, "tl")),
    ("2 Esslöffel Öl", ("Öl", 2, "el")),
    ("1 tsp Zimt", ("Zimt", 1, "tl")),
    ("2 Eier", ("Eier", 2, "x")),  # 'el' prefix inside a word is not a unit
])
def test_parse_line(line, expected):
    p = parse_ingredient_line(line)
    assert (p["name"], p["quantity"], p["unit"]) == expected


@pytest.mark.parametrize("line", ["", "   ", "Für den Teig:", "- ", "200 g"])
def test_parse_line_skipped(line):
    assert parse_ingredient_line(line) is None


def test_parse_ingredients_dedupes_and_skips_headers():
    text = "Teig:\n2 Eier\n\n300 g Mehl\n1 Ei\n2 eier\n"
    assert [p["name"] for p in parse_ingredients(text)] == ["Eier", "Mehl", "Ei"]
