"""Colour parsing, conversion and clustering for design-catalog scripts.

Standard library only. Parses every colour syntax a browser's computed style
can return (rgb/rgba, hex, hsl, oklch, oklab, lab, lch, color(srgb|srgb-linear|display-p3),
named colours, transparent) into sRGB + alpha, converts to OKLab for perceptual
distance, and matches colours against the Tailwind default palettes.
"""

from __future__ import annotations

import math
import os
import re
import sys
from typing import Iterable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import tailwind_palette
except ImportError:  # pragma: no cover
    tailwind_palette = None

NAMED = {
    "aliceblue": "f0f8ff", "antiquewhite": "faebd7", "aqua": "00ffff", "aquamarine": "7fffd4",
    "azure": "f0ffff", "beige": "f5f5dc", "bisque": "ffe4c4", "black": "000000",
    "blanchedalmond": "ffebcd", "blue": "0000ff", "blueviolet": "8a2be2", "brown": "a52a2a",
    "burlywood": "deb887", "cadetblue": "5f9ea0", "chartreuse": "7fff00", "chocolate": "d2691e",
    "coral": "ff7f50", "cornflowerblue": "6495ed", "cornsilk": "fff8dc", "crimson": "dc143c",
    "cyan": "00ffff", "darkblue": "00008b", "darkcyan": "008b8b", "darkgoldenrod": "b8860b",
    "darkgray": "a9a9a9", "darkgreen": "006400", "darkgrey": "a9a9a9", "darkkhaki": "bdb76b",
    "darkmagenta": "8b008b", "darkolivegreen": "556b2f", "darkorange": "ff8c00",
    "darkorchid": "9932cc", "darkred": "8b0000", "darksalmon": "e9967a", "darkseagreen": "8fbc8f",
    "darkslateblue": "483d8b", "darkslategray": "2f4f4f", "darkslategrey": "2f4f4f",
    "darkturquoise": "00ced1", "darkviolet": "9400d3", "deeppink": "ff1493", "deepskyblue": "00bfff",
    "dimgray": "696969", "dimgrey": "696969", "dodgerblue": "1e90ff", "firebrick": "b22222",
    "floralwhite": "fffaf0", "forestgreen": "228b22", "fuchsia": "ff00ff", "gainsboro": "dcdcdc",
    "ghostwhite": "f8f8ff", "gold": "ffd700", "goldenrod": "daa520", "gray": "808080",
    "green": "008000", "greenyellow": "adff2f", "grey": "808080", "honeydew": "f0fff0",
    "hotpink": "ff69b4", "indianred": "cd5c5c", "indigo": "4b0082", "ivory": "fffff0",
    "khaki": "f0e68c", "lavender": "e6e6fa", "lavenderblush": "fff0f5", "lawngreen": "7cfc00",
    "lemonchiffon": "fffacd", "lightblue": "add8e6", "lightcoral": "f08080", "lightcyan": "e0ffff",
    "lightgoldenrodyellow": "fafad2", "lightgray": "d3d3d3", "lightgreen": "90ee90",
    "lightgrey": "d3d3d3", "lightpink": "ffb6c1", "lightsalmon": "ffa07a", "lightseagreen": "20b2aa",
    "lightskyblue": "87cefa", "lightslategray": "778899", "lightslategrey": "778899",
    "lightsteelblue": "b0c4de", "lightyellow": "ffffe0", "lime": "00ff00", "limegreen": "32cd32",
    "linen": "faf0e6", "magenta": "ff00ff", "maroon": "800000", "mediumaquamarine": "66cdaa",
    "mediumblue": "0000cd", "mediumorchid": "ba55d3", "mediumpurple": "9370db",
    "mediumseagreen": "3cb371", "mediumslateblue": "7b68ee", "mediumspringgreen": "00fa9a",
    "mediumturquoise": "48d1cc", "mediumvioletred": "c71585", "midnightblue": "191970",
    "mintcream": "f5fffa", "mistyrose": "ffe4e1", "moccasin": "ffe4b5", "navajowhite": "ffdead",
    "navy": "000080", "oldlace": "fdf5e6", "olive": "808000", "olivedrab": "6b8e23",
    "orange": "ffa500", "orangered": "ff4500", "orchid": "da70d6", "palegoldenrod": "eee8aa",
    "palegreen": "98fb98", "paleturquoise": "afeeee", "palevioletred": "db7093",
    "papayawhip": "ffefd5", "peachpuff": "ffdab9", "peru": "cd853f", "pink": "ffc0cb",
    "plum": "dda0dd", "powderblue": "b0e0e6", "purple": "800080", "rebeccapurple": "663399",
    "red": "ff0000", "rosybrown": "bc8f8f", "royalblue": "4169e1", "saddlebrown": "8b4513",
    "salmon": "fa8072", "sandybrown": "f4a460", "seagreen": "2e8b57", "seashell": "fff5ee",
    "sienna": "a0522d", "silver": "c0c0c0", "skyblue": "87ceeb", "slateblue": "6a5acd",
    "slategray": "708090", "slategrey": "708090", "snow": "fffafa", "springgreen": "00ff7f",
    "steelblue": "4682b4", "tan": "d2b48c", "teal": "008080", "thistle": "d8bfd8", "tomato": "ff6347",
    "turquoise": "40e0d0", "violet": "ee82ee", "wheat": "f5deb3", "white": "ffffff",
    "whitesmoke": "f5f5f5", "yellow": "ffff00", "yellowgreen": "9acd32",
}

_FUNC_RE = re.compile(r"^([a-z-]+)\((.*)\)$", re.S)
_NUM_RE = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$", re.I)

Color = tuple[float, float, float, float]  # r, g, b in 0..1 (may be out of gamut), alpha 0..1


def _num(tok: str, scale: float = 1.0, pct_scale: float | None = None) -> float:
    """Parse a number or percentage token. pct_scale is the value 100% maps to."""
    tok = tok.strip()
    if tok == "none":
        return 0.0
    if tok.endswith("%"):
        v = float(tok[:-1]) / 100.0
        return v * (pct_scale if pct_scale is not None else scale)
    if tok.endswith("deg"):
        return float(tok[:-3])
    if tok.endswith("rad"):
        return math.degrees(float(tok[:-3]))
    if tok.endswith("turn"):
        return float(tok[:-4]) * 360.0
    if tok.endswith("grad"):
        return float(tok[:-4]) * 0.9
    return float(tok)


def _split_args(inner: str) -> tuple[list[str], str | None]:
    """Split function arguments on commas, spaces and a slash. Returns (values, alpha)."""
    inner = inner.strip()
    alpha = None
    if "/" in inner:
        inner, a = inner.rsplit("/", 1)
        alpha = a.strip()
    parts = [p for p in re.split(r"[,\s]+", inner.strip()) if p]
    return parts, alpha


def _alpha(tok: str | None) -> float:
    if tok is None:
        return 1.0
    return max(0.0, min(1.0, _num(tok, 1.0, 1.0)))


def srgb_to_linear(c: float) -> float:
    c = max(-1.0, min(2.0, c))
    sign = -1.0 if c < 0 else 1.0
    c = abs(c)
    return sign * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: float) -> float:
    sign = -1.0 if c < 0 else 1.0
    c = abs(c)
    return sign * (c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


def _mat(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


_XYZ65_TO_LIN_SRGB = [[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560], [0.0556434, -0.2040259, 1.0572252]]
_LIN_P3_TO_XYZ65 = [[0.4865709, 0.2656677, 0.1982173], [0.2289746, 0.6917385, 0.0792869], [0.0, 0.0451134, 1.0439444]]
_D50_TO_D65 = [[0.9555766, -0.0230393, 0.0631636], [-0.0282895, 1.0099416, 0.0210077], [0.0122982, -0.0204830, 1.3299098]]


def oklab_to_linear_srgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def linear_srgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _lab_to_xyz50(L: float, a: float, b: float) -> tuple[float, float, float]:
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    e, k = 216 / 24389, 24389 / 27

    def finv(t):
        return t ** 3 if t ** 3 > e else (116 * t - 16) / k

    return (0.96422 * finv(fx), 1.0 * finv(fy), 0.82521 * finv(fz))


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    h = (h % 360) / 360.0
    if s == 0:
        return (l, l, l)
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def hue(t):
        t %= 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    return (hue(h + 1 / 3), hue(h), hue(h - 1 / 3))


def parse(value: str) -> Color | None:
    """Parse a CSS colour string into (r, g, b, a) with channels in 0..1. None if not a colour."""
    if value is None:
        return None
    v = value.strip().lower()
    if not v:
        return None
    if v in ("transparent", "rgba(0, 0, 0, 0)"):
        return (0.0, 0.0, 0.0, 0.0)
    if v in ("currentcolor", "inherit", "initial", "unset", "none", "auto"):
        return None
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) not in (6, 8) or not re.fullmatch(r"[0-9a-f]+", h):
            return None
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    if v in NAMED:
        return parse("#" + NAMED[v])
    m = _FUNC_RE.match(v)
    if not m:
        return None
    fn, inner = m.group(1), m.group(2)
    try:
        if fn in ("rgb", "rgba"):
            parts, alpha = _split_args(inner)
            if len(parts) == 4 and alpha is None:
                alpha = parts.pop()
            if len(parts) != 3:
                return None
            r, g, b = (_num(p, 1.0, 1.0) if p.endswith("%") else float(p) / 255 for p in parts)
            return (r, g, b, _alpha(alpha))
        if fn in ("hsl", "hsla"):
            parts, alpha = _split_args(inner)
            if len(parts) == 4 and alpha is None:
                alpha = parts.pop()
            if len(parts) != 3:
                return None
            h = _num(parts[0])
            s = _num(parts[1], 1.0, 1.0) if parts[1].endswith("%") else float(parts[1]) / 100
            l = _num(parts[2], 1.0, 1.0) if parts[2].endswith("%") else float(parts[2]) / 100
            r, g, b = _hsl_to_rgb(h, s, l)
            return (r, g, b, _alpha(alpha))
        if fn == "oklch":
            parts, alpha = _split_args(inner)
            L = _num(parts[0], 1.0, 1.0)
            C = _num(parts[1], 1.0, 0.4)
            h = _num(parts[2]) if len(parts) > 2 else 0.0
            a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
            r, g, bb = (linear_to_srgb(c) for c in oklab_to_linear_srgb(L, a, b))
            return (r, g, bb, _alpha(alpha))
        if fn == "oklab":
            parts, alpha = _split_args(inner)
            L = _num(parts[0], 1.0, 1.0)
            a = _num(parts[1], 1.0, 0.4)
            b = _num(parts[2], 1.0, 0.4)
            r, g, bb = (linear_to_srgb(c) for c in oklab_to_linear_srgb(L, a, b))
            return (r, g, bb, _alpha(alpha))
        if fn in ("lab", "lch"):
            parts, alpha = _split_args(inner)
            L = _num(parts[0], 1.0, 100.0)
            if fn == "lab":
                a = _num(parts[1], 1.0, 125.0)
                b = _num(parts[2], 1.0, 125.0)
            else:
                C = _num(parts[1], 1.0, 150.0)
                h = _num(parts[2]) if len(parts) > 2 else 0.0
                a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
            xyz50 = _lab_to_xyz50(L, a, b)
            xyz65 = _mat(_D50_TO_D65, xyz50)
            lin = _mat(_XYZ65_TO_LIN_SRGB, xyz65)
            r, g, bb = (linear_to_srgb(c) for c in lin)
            return (r, g, bb, _alpha(alpha))
        if fn == "color":
            parts, alpha = _split_args(inner)
            space, chans = parts[0], [_num(p, 1.0, 1.0) for p in parts[1:4]]
            if space == "srgb":
                return (*chans, _alpha(alpha))
            if space == "srgb-linear":
                return (*(linear_to_srgb(c) for c in chans), _alpha(alpha))
            if space == "display-p3":
                lin_p3 = [srgb_to_linear(c) for c in chans]
                xyz = _mat(_LIN_P3_TO_XYZ65, lin_p3)
                lin = _mat(_XYZ65_TO_LIN_SRGB, xyz)
                return (*(linear_to_srgb(c) for c in lin), _alpha(alpha))
            return None
    except (ValueError, IndexError):
        return None
    return None


def to_oklab(c: Color) -> tuple[float, float, float]:
    return linear_srgb_to_oklab(*(srgb_to_linear(x) for x in c[:3]))


def to_oklch(c: Color) -> tuple[float, float, float]:
    L, a, b = to_oklab(c)
    C = math.hypot(a, b)
    h = math.degrees(math.atan2(b, a)) % 360 if C > 1e-4 else 0.0
    return (L, C, h)


def delta(c1: Color, c2: Color) -> float:
    """Perceptual distance in OKLab (Euclidean). ~0.01 is barely visible, 0.03 is a clear but small step."""
    a, b = to_oklab(c1), to_oklab(c2)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def to_hex(c: Color, with_alpha: bool = True) -> str:
    r, g, b = (round(clamp01(x) * 255) for x in c[:3])
    s = f"#{r:02x}{g:02x}{b:02x}"
    if with_alpha and c[3] < 0.999:
        s += f"{round(c[3] * 255):02x}"
    return s


def to_rgb_string(c: Color) -> str:
    r, g, b = (round(clamp01(x) * 255) for x in c[:3])
    if c[3] < 0.999:
        return f"rgba({r}, {g}, {b}, {round(c[3], 3):g})"
    return f"rgb({r}, {g}, {b})"


def to_oklch_string(c: Color) -> str:
    L, C, h = to_oklch(c)
    s = f"oklch({L * 100:.1f}% {C:.3f} {h:.1f})"
    if c[3] < 0.999:
        s = s[:-1] + f" / {round(c[3], 3):g})"
    return s


def is_neutral(c: Color, max_chroma: float = 0.04) -> bool:
    return to_oklch(c)[1] <= max_chroma


def describe(c: Color) -> str:
    """Human words: 'light cool grey', 'dark indigo', 'white'."""
    L, C, h = to_oklch(c)
    if c[3] < 0.05:
        return "transparent"
    if C <= 0.04:
        if L > 0.98:
            return "white"
        if L < 0.12:
            return "black"
        tone = "light " if L > 0.8 else "mid " if L > 0.45 else "dark "
        warmth = "" if C < 0.006 else ("warm " if 40 <= h <= 110 else "cool ")
        return f"{tone}{warmth}grey".replace("  ", " ")
    hues = [
        (15, "red"), (40, "orange"), (75, "amber"), (100, "yellow"), (130, "lime"), (155, "green"),
        (175, "teal"), (205, "cyan"), (235, "sky"), (265, "blue"), (285, "indigo"), (305, "violet"),
        (330, "purple"), (350, "pink"), (361, "rose"),
    ]
    name = next(n for lim, n in hues if h < lim)
    tone = "very light " if L > 0.9 else "light " if L > 0.75 else "" if L > 0.5 else "dark "
    sat = "muted " if C < 0.08 else ""
    return f"{tone}{sat}{name}".strip()


_PALETTE_CACHE: list[tuple[str, str, str, Color]] | None = None


def _palette() -> list[tuple[str, str, str, Color]]:
    global _PALETTE_CACHE
    if _PALETTE_CACHE is None:
        entries: list[tuple[str, str, str, Color]] = []
        if tailwind_palette is not None:
            for version, table in (("v3", tailwind_palette.V3), ("v4", tailwind_palette.V4)):
                for family, shades in table.items():
                    for shade, css in shades.items():
                        c = parse(css)
                        if c:
                            entries.append((version, family, shade, c))
            for version in ("v3", "v4"):
                entries.append((version, "white", "", (1.0, 1.0, 1.0, 1.0)))
                entries.append((version, "black", "", (0.0, 0.0, 0.0, 1.0)))
        _PALETTE_CACHE = entries
    return _PALETTE_CACHE


def nearest_tailwind(c: Color, max_delta: float = 0.012) -> list[dict]:
    """Tailwind palette entries within max_delta of c, nearest first. Each: {name, version, delta}."""
    if c[3] < 0.05:
        return []
    opaque = (c[0], c[1], c[2], 1.0)
    hits = []
    for version, family, shade, pc in _palette():
        d = delta(opaque, pc)
        if d <= max_delta:
            name = f"{family}-{shade}" if shade else family
            hits.append({"name": name, "version": version, "delta": round(d, 4)})
    hits.sort(key=lambda h: h["delta"])
    # one entry per name, best version first
    seen, out = set(), []
    for h in hits:
        if h["name"] in seen:
            continue
        seen.add(h["name"])
        out.append(h)
    return out


def _is_anchor(c: Color) -> bool:
    return all(x >= 0.999 for x in c[:3]) or all(x <= 0.001 for x in c[:3])


def compatible(c1: Color, c2: Color) -> bool:
    """False when two colours should never be treated as one even if close in OKLab:
    a tint next to a grey (chroma differs), or two clearly coloured values of different hue."""
    la, ca, ha = to_oklch(c1)
    lb, cb, hb = to_oklch(c2)
    hue_diff = abs((ha - hb + 180) % 360 - 180)
    light = max(la, lb) > 0.7
    if light and abs(ca - cb) > 0.018 and max(ca, cb) > 0.025:
        return False  # a tint next to a grey
    if min(ca, cb) > 0.03 and hue_diff > 30:
        return False  # two colours of different hue
    if light and min(ca, cb) > 0.012 and hue_diff > 40:
        return False  # two pale tints of different hue
    return True


def cluster(items: Iterable[tuple[str, int]], threshold: float = 0.03) -> list[dict]:
    """Greedy perceptual clustering.

    items: (css colour string, weight). Returns clusters sorted by total weight, each
    {"members": [{"value", "weight", "hex", "parsed"}...], "survivor": value, "hex": ...}.
    Colours with different alpha never share a cluster. Unparseable values are skipped.
    """
    parsed = []
    for value, weight in items:
        c = parse(value)
        if c is None:
            continue
        parsed.append((value, weight, c))
    parsed.sort(key=lambda t: -t[1])
    clusters: list[dict] = []
    for value, weight, c in parsed:
        placed = False
        anchor = _is_anchor(c)
        for cl in clusters:
            rep = cl["members"][0]["parsed"]
            if abs(rep[3] - c[3]) > 0.02:
                continue
            if anchor or _is_anchor(rep):
                continue  # pure white and pure black never absorb or join a neighbour
            if not compatible(rep, c):
                continue
            limit = threshold
            if to_oklab(rep)[0] > 0.93 and to_oklab(c)[0] > 0.93:
                limit = threshold * 0.5  # steps between near-whites are perceptually tiny but intentional
            if delta(rep, c) <= limit:
                cl["members"].append({"value": value, "weight": weight, "hex": to_hex(c), "parsed": c})
                placed = True
                break
        if not placed:
            clusters.append({"members": [{"value": value, "weight": weight, "hex": to_hex(c), "parsed": c}]})
    for cl in clusters:
        cl["members"].sort(key=lambda m: -m["weight"])
        cl["survivor"] = cl["members"][0]["value"]
        cl["hex"] = cl["members"][0]["hex"]
        cl["weight"] = sum(m["weight"] for m in cl["members"])
        cl["parsed"] = cl["members"][0]["parsed"]
    clusters.sort(key=lambda cl: -cl["weight"])
    return clusters


if __name__ == "__main__":  # small manual check
    import sys

    for arg in sys.argv[1:]:
        c = parse(arg)
        if c is None:
            print(arg, "-> not a colour")
            continue
        print(arg, "->", to_hex(c), to_oklch_string(c), describe(c), nearest_tailwind(c)[:3])
