"""Block unsourced numbers in stat posts.

Every number written on a stat slide must exist in data/lighthouse-2026.json (allowing the
usual conversions: ms to seconds, rounding to 0 or 1 decimal) or in the small list of
fixed reference numbers below. Returns a list of check dicts like the renderer's."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXED = {2.5, 4, 10, 50, 90, 100, 2026, 15, 1, 2, 3}  # Google thresholds, score bands, year, CTA "15 minutes", small counts


def allowed_numbers():
    vals = set(FIXED)
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            v = float(o)
            for x in (v, v / 1000):  # ms -> s
                vals.add(round(x, 1)); vals.add(round(x)); vals.add(round(x, 2))
            vals.add(round(100 - v, 1))  # "x% did not pass" is the complement of a pass rate
    walk(json.loads((ROOT / "data" / "lighthouse-2026.json").read_text()))
    return vals


NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)")


def numbers_in(text):
    out = []
    for m in NUM.finditer(text):
        raw = m.group(1)
        out.append((raw, float(raw.replace(",", ""))))
    return out


def check(spec):
    if spec.get("format") not in ("stat-carousel", "stat-video"):
        return []
    checks = []
    if not spec.get("sources"):
        checks.append({"level": "error", "msg": "Stat post has no sources"})
    ok = allowed_numbers()
    texts = []
    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("type", "secs", "size", "max", "dots"): continue
                walk(v, k)
        elif isinstance(o, list):
            for v in o: walk(v, key)
        elif isinstance(o, str):
            texts.append(o)
        elif isinstance(o, (int, float)) and key == "value":
            texts.append(str(o))
    walk(spec.get("data", {}))
    for t in texts:
        for raw, v in numbers_in(t):
            if v in ok or round(v, 1) in ok:
                continue
            checks.append({"level": "error", "msg": f'Number "{raw}" in "{t[:70]}" is not in the data bank'})
    return checks
