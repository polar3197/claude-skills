#!/usr/bin/env python3
"""Validate the marketplace, plugin manifests and every SKILL.md in this repo. Stdlib only."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
errors = []


def err(msg):
    errors.append(msg)


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


market = ROOT / ".claude-plugin" / "marketplace.json"
try:
    mk = json.loads(market.read_text())
except Exception as e:  # noqa: BLE001
    print(f"FAIL {market}: {e}")
    sys.exit(1)
for k in ("name", "owner", "plugins"):
    if k not in mk:
        err(f"marketplace.json: missing {k}")
if not NAME_RE.match(mk.get("name", "")):
    err("marketplace.json: name must be lowercase kebab-case")
seen = set()
for i, p in enumerate(mk.get("plugins", [])):
    name, src = p.get("name"), p.get("source")
    if not name or not src:
        err(f"plugins[{i}]: needs name and source")
        continue
    if name in seen:
        err(f"plugins[{i}]: duplicate plugin name {name}")
    seen.add(name)
    if not isinstance(src, str) or ".." in src:
        err(f"{name}: source must be a relative path without '..'")
        continue
    pdir = (ROOT / src).resolve()
    manifest = pdir / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        err(f"{name}: missing {manifest.relative_to(ROOT)}")
        continue
    pj = json.loads(manifest.read_text())
    if pj.get("name") != name:
        err(f"{name}: plugin.json name {pj.get('name')!r} must equal the marketplace entry name")
    if not re.match(r"^\d+\.\d+\.\d+", pj.get("version", "")):
        err(f"{name}: plugin.json needs a semver version")
    skills = sorted((pdir / "skills").glob("*/SKILL.md"))
    if not skills:
        err(f"{name}: no skills/*/SKILL.md found")
    for s in skills:
        fm = frontmatter(s.read_text())
        rel = s.relative_to(ROOT)
        if fm is None:
            err(f"{rel}: missing YAML frontmatter")
            continue
        if fm.get("name") != s.parent.name:
            err(f"{rel}: frontmatter name {fm.get('name')!r} must match its directory {s.parent.name!r}")
        if not NAME_RE.match(fm.get("name", "")) or "claude" in fm.get("name", "") or "anthropic" in fm.get("name", ""):
            err(f"{rel}: name must be kebab-case, <=64 chars, and not contain 'claude' or 'anthropic'")
        d = fm.get("description", "")
        if not d:
            err(f"{rel}: description is required")
        elif len(d) > 1024 or "<" in d or ">" in d:
            err(f"{rel}: description must be <=1024 chars with no angle brackets")
        for link in re.findall(r"\]\(((?!https?:)[^)#]+)\)", s.read_text()):
            if not (s.parent / link).exists():
                err(f"{rel}: broken relative link {link}")
        print(f"ok   {rel}")

if errors:
    for e in errors:
        print(f"FAIL {e}")
    sys.exit(1)
print("all skills valid")
