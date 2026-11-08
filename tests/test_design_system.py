"""Design system foundation: local fonts and colour tokens."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
BASE_CSS = (STATIC / "css" / "base.css").read_text(encoding="utf-8")

def token(name):
    return re.search(rf"--color-{name}:\s*(#[0-9a-fA-F]{{6}})", BASE_CSS).group(1)


def contrast(foreground, background):
    """WCAG 2.x contrast ratio between two #rrggbb colours."""

    def luminance(hex_colour):
        channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted([luminance(foreground), luminance(background)], reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# --- fonts ---


def test_exactly_two_local_woff2_fonts_with_swap():
    faces = re.findall(r"@font-face\s*\{(.*?)\}", BASE_CSS, re.S)

    assert len(faces) == 2
    for face in faces:
        assert re.search(r'url\("\.\./fonts/[\w-]+\.woff2"\)\s*format\("woff2"\)', face)
        assert "font-display: swap" in face
    assert sorted(p.name for p in (STATIC / "fonts").glob("*.woff2")) == [
        "archivo-variable.woff2",
        "barlow-condensed-700.woff2",
    ]


def test_font_files_are_served(client):
    for url in re.findall(r'url\("\.\./fonts/([\w-]+\.woff2)"\)', BASE_CSS):
        response = client.get(f"/static/fonts/{url}")
        assert response.status_code == 200
        assert response.data[:4] == b"wOF2"  # a real woff2 file, not an HTML error page


def test_fonts_come_with_their_licence():
    for name in ("OFL-archivo.txt", "OFL-barlow-condensed.txt"):
        assert "SIL Open Font License" in (STATIC / "fonts" / name).read_text(encoding="utf-8")


def test_csp_allows_fonts_from_self(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    directives = {
        part.split()[0]: part.split()[1:] for part in csp.split(";") if part.strip()
    }
    font_sources = directives.get("font-src", directives.get("default-src"))

    assert "'self'" in font_sources


# --- colour tokens ---


@pytest.mark.parametrize(
    "text, background",
    [
        ("ink", "surface"), ("ink", "page"), ("ink", "tile"),
        ("ink-soft", "surface"), ("ink-soft", "page"),
        ("muted", "surface"), ("muted", "page"), ("muted", "tile"),
        ("accent-dark", "surface"),
        ("surface", "ink"),  # white text on the dark bands
        ("accent", "ink"),  # orange prices on the dark featured band
    ],
)
def test_text_colour_pairs_meet_wcag_aa(text, background):
    assert contrast(token(text), token(background)) >= 4.5


def test_signal_orange_is_too_light_for_small_text_on_white():
    """Documents the rule in base.css: --color-accent is never small text on white."""
    assert contrast(token("accent"), token("surface")) < 4.5


# --- pattern ---


def test_contour_pattern_is_a_small_served_svg(client):
    response = client.get("/static/img/patterns/contour.svg")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert len(response.data) < 4096
