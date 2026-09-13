#!/usr/bin/env python3
"""`as` plugin validator — structural + content invariants.

Runnable locally (`python3 ci/validate.py`) and in CI. Pure stdlib. Exits
non-zero on any failure; prints one line per check.

Checks:
  1. Manifests parse and agree: plugin.json name and NO version anywhere on the
     Claude side (installs track the commit SHA), marketplace.json name/entry,
     Codex plugin.json (name, semver, skills == "./skills"), Codex marketplace.
  2. Parity: skills/ minus CLAUDE_ONLY == skills-codex/skills/.
  3. SKILL.md frontmatter: name == dir (bare, no plugin prefix), description
     present; Claude: description+when_to_use <= 1536 chars; Codex: description
     <= 1024 chars and no '<'/'>'; body <= MAX_SKILL_LINES.
  4. agents/*.md: name == stem, no ':', description, `tools:` (not allowed-tools).
  5. Path hygiene: script/role/workflow invocations in Claude SKILL.md go through
     ${CLAUDE_SKILL_DIR} and resolve; Codex SKILL.md never mentions
     ${CLAUDE_SKILL_DIR} (Codex does not expand it).
  6. Names: no stale names (iron-skills, deleted skills, old aliases); every
     `/as:<skill>` mention names a real skill; every `as:<agent>` names a real agent.
  7. Codex packaging: shared assets byte-identical to skills/; no workflows/
     under skills-codex.
  8. Syntax: py_compile, `node --check` on wrapped *.workflow.js (no import()),
     `bash -n` on *.sh.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
CODEX = ROOT / "skills-codex" / "skills"
AGENTS = ROOT / "agents"
CLAUDE_ONLY = {"babysit"}          # no Codex variant (needs /loop)
MAX_SKILL_LINES = 300
CLAUDE_DESC_CAP = 1536             # description + when_to_use are truncated here in listings
CODEX_DESC_CAP = 1024              # OpenAI's quick_validate.py cap
# Stale names, as command/path forms only — prose ("formerly iron-skills", a
# third-party attribution) is legitimate, so these patterns must not match it.
STALE = {
    "old plugin name": re.compile(r"iron-skills:|/iron-skills\b|@iron-skills\b"),
    "old repo names": re.compile(r"\bagent-skills\b|\bagent-workflow\b"),
    "deleted skills": re.compile(r"/(as:)?(blueprint|goal-prep|herdr|ship|thermo)\b"
                                r"|skills(-codex)?/(blueprint|goal-prep|herdr|ship|thermo)\b"),
    "old skill aliases": re.compile(r"/(as:)?(accept|clarify|plan-rewrite)\b"
                                    r"|/as:extract\b(?!-links)|\bags:|agent-goal-stack"),
    "third-party skill refs": re.compile(r"mattpocock"),
}

failures, checks = [], 0


def record(ok, name, detail=""):
    global checks
    checks += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def section(title):
    print(f"\n== {title} ==")


def read(p):
    return p.read_text(encoding="utf-8", errors="ignore")


def rel(p):
    return p.relative_to(ROOT)


def frontmatter(text):
    """Minimal YAML frontmatter extractor (inline + block scalars, flow lists as text)."""
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return None
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    fm, i, block = {}, 0, lines[1:end]
    while i < len(block):
        m = re.match(r"^([A-Za-z0-9_-]+):(.*)$", block[i])
        if m:
            key, inline = m.group(1), m.group(2).strip()
            vals = [] if inline in ("", ">", "|", "|-", ">-") else [inline]
            j = i + 1
            while j < len(block) and (block[j].startswith((" ", "\t")) or not block[j].strip()):
                if block[j].strip():
                    vals.append(block[j].strip())
                j += 1
            fm[key] = " ".join(vals).strip()
            i = j
        else:
            i += 1
    return fm


def skill_dirs(root):
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def first_error(stderr):
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    return next((ln for ln in lines if "Error" in ln), lines[0] if lines else "")


# ── 1. manifests ──
section("manifests")
def load(p, label):
    try:
        d = json.loads(read(p))
        record(True, f"{label} parses")
        return d
    except Exception as e:  # noqa: BLE001
        record(False, f"{label} parses", str(e))
        return None

plugin = load(ROOT / ".claude-plugin" / "plugin.json", "plugin.json")
market = load(ROOT / ".claude-plugin" / "marketplace.json", "marketplace.json")
cx = load(ROOT / "skills-codex" / ".codex-plugin" / "plugin.json", "codex plugin.json")
cmkt = load(ROOT / ".agents" / "plugins" / "marketplace.json", "codex marketplace.json")
NAME = (plugin or {}).get("name")
if plugin and market:
    entry = (market.get("plugins") or [{}])[0]
    record(NAME and NAME == market.get("name") == entry.get("name"), "plugin name agrees across manifests",
           f"{NAME} / {market.get('name')} / {entry.get('name')}")
    # No version anywhere on the Claude side: Claude Code then tracks the commit
    # SHA, so every push to main reaches installed users. A version field would
    # re-pin them until it was bumped by hand.
    record("version" not in plugin, "plugin.json has NO version (installs track the commit SHA)")
    record("version" not in entry, "marketplace entry has NO version")
    record(entry.get("source") == "./", 'marketplace entry source == "./"', str(entry.get("source")))
    record("skills" not in plugin and "agents" not in plugin, "plugin.json relies on default skills/ + agents/ discovery")
if cx and plugin:
    # Codex needs a semver (OpenAI's validator rejects a manifest without one),
    # so the two manifests agree on the name only.
    record(cx.get("name") == NAME, "codex plugin.json name agrees", str(cx.get("name")))
    record(bool(re.fullmatch(r"\d+\.\d+\.\d+", cx.get("version") or "")),
           "codex plugin.json has a semver", str(cx.get("version")))
    record(cx.get("skills") == "./skills", 'codex plugin.json skills == "./skills"', str(cx.get("skills")))
    record(isinstance(cx.get("interface"), dict) and cx["interface"].get("displayName"), "codex plugin.json has interface block")
if cmkt and NAME:
    e = (cmkt.get("plugins") or [{}])[0]
    record(cmkt.get("name") == NAME and e.get("name") == NAME and (e.get("source") or {}).get("path") == "./skills-codex",
           'codex marketplace name/path', f"{cmkt.get('name')} / {e.get('name')} / {(e.get('source') or {}).get('path')}")

# ── 2. parity ──
section("skills ↔ skills-codex parity")
sk = {p.name for p in skill_dirs(SKILLS)}
ck = {p.name for p in skill_dirs(CODEX)} if CODEX.exists() else set()
record((sk - CLAUDE_ONLY) == ck, "skills-codex/skills mirrors skills/ (Claude-only exempt)",
       f"claude-extra={sorted((sk - CLAUDE_ONLY) - ck)} codex-only={sorted(ck - (sk - CLAUDE_ONLY))}")
record(CLAUDE_ONLY <= sk and not (CLAUDE_ONLY & ck), "Claude-only skills present in skills/, absent from Codex tree")

# ── 3. SKILL.md frontmatter ──
section("SKILL.md frontmatter + size")
for tree, root, is_codex in (("skills", SKILLS, False), ("skills-codex/skills", CODEX, True)):
    for d in skill_dirs(root):
        f = d / "SKILL.md"
        label = f"{tree}/{d.name}/SKILL.md"
        if not f.exists():
            record(False, label, "missing")
            continue
        text = read(f)
        fm = frontmatter(text)
        if fm is None:
            record(False, label, "no frontmatter")
            continue
        problems = []
        if fm.get("name") != d.name:
            problems.append(f"name={fm.get('name')!r} != dir")
        desc = fm.get("description", "")
        if not desc:
            problems.append("description missing")
        if is_codex:
            if len(desc) > CODEX_DESC_CAP:
                problems.append(f"description {len(desc)} > {CODEX_DESC_CAP}")
            if "<" in desc or ">" in desc:
                problems.append("description contains < or >")
            if "when_to_use" in fm:
                problems.append("when_to_use is ignored by Codex — fold into description")
        else:
            total = len(desc) + len(fm.get("when_to_use", ""))
            if total > CLAUDE_DESC_CAP:
                problems.append(f"description+when_to_use {total} > {CLAUDE_DESC_CAP}")
        n = text.count("\n") + 1
        if n > MAX_SKILL_LINES:
            problems.append(f"{n} lines > {MAX_SKILL_LINES}")
        record(not problems, label, "; ".join(problems) if problems else f"{n} lines")

# ── 4. agents ──
section("agents/*.md frontmatter")
agent_names = set()
for f in sorted(AGENTS.glob("*.md")) if AGENTS.exists() else []:
    fm = frontmatter(read(f)) or {}
    problems = []
    if fm.get("name") != f.stem:
        problems.append(f"name={fm.get('name')!r} != {f.stem!r}")
    if ":" in (fm.get("name") or ""):
        problems.append("name contains ':'")
    if not fm.get("description"):
        problems.append("description missing")
    if "allowed-tools" in fm:
        problems.append("uses allowed-tools (subagents use `tools:`)")
    if "tools" not in fm:
        problems.append("no tools: allowlist")
    agent_names.add(f.stem)
    record(not problems, f"agents/{f.name}", "; ".join(problems))

# ── 5. path hygiene ──
section("path hygiene (${CLAUDE_SKILL_DIR})")
INVOKE = re.compile(r"(?:\bbash\s+|\bpython3\s+|\bsh\s+|scriptPath:\s*|\bsource\s+)[\"'`]?(?P<path>[^\s\"'`]+)")
# Role/reference files are usually named in prose inside backticks, not run — a bare
# `roles/x.md` is the same cwd-relative bug as a bare `bash scripts/x.sh`.
PROSE_PATH = re.compile(r"`(?P<path>(?:\./)?(?:scripts|roles|workflows|references)/[\w./-]+)`")
for tree, root, is_codex in (("skills", SKILLS, False), ("skills-codex/skills", CODEX, True)):
    for d in skill_dirs(root):
        f = d / "SKILL.md"
        if not f.exists():
            continue
        text = read(f)
        bad = []
        if is_codex:
            if "${CLAUDE_SKILL_DIR}" in text or "$CLAUDE_SKILL_DIR" in text:
                bad.append("mentions ${CLAUDE_SKILL_DIR} (Codex does not expand it)")
        else:
            for n, line in enumerate(text.splitlines(), 1):
                for m in list(INVOKE.finditer(line)) + list(PROSE_PATH.finditer(line)):
                    path = m.group("path")
                    if re.match(r"(\./)?(scripts|roles|workflows|references)/", path):
                        bad.append(f"L{n}: `{path}` must use ${{CLAUDE_SKILL_DIR}}/…")
                for m in re.finditer(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", line):
                    if not (d / m.group(1)).exists():
                        bad.append(f"L{n}: ${{CLAUDE_SKILL_DIR}}/{m.group(1)} does not exist")
        record(not bad, f"{tree}/{d.name}/SKILL.md", "; ".join(bad[:4]))

CLAUDE_ONLY_TOKENS = re.compile(r"AskUserQuestion|\bAgent\(|\bWorkflow\(|ScheduleWakeup|CronCreate|"
                                r"PushNotification|TaskStop|EnterWorktree|\$\{CLAUDE_(SKILL_DIR|PLUGIN_ROOT)\}|"
                                r"subagent_type|/loop\b")
# `codex exec` is just a CLI the Claude host may shell out to; only the in-process
# multi-agent primitives are Codex-host-only.
CODEX_ONLY_TOKENS = re.compile(r"spawn_agent|wait_agent|close_agent")
for tree, root, forbidden, why in (
    ("skills-codex/skills", CODEX, CLAUDE_ONLY_TOKENS, "Claude-only mechanism in a Codex skill"),
    ("skills", SKILLS, CODEX_ONLY_TOKENS, "Codex-only mechanism in a Claude skill"),
):
    for d in skill_dirs(root):
        f = d / "SKILL.md"
        if not f.exists():
            continue
        hits = []
        for n, line in enumerate(read(f).splitlines(), 1):
            m = forbidden.search(line)
            # A line that explicitly says the mechanism is absent is documentation, not use.
            if m and not re.search(r"\bno\b|\bnot\b|without|absent|unavailable|instead of", line, re.I):
                hits.append(f"L{n}: {m.group(0)}")
        record(not hits, f"{why}: {tree}/{d.name}", "; ".join(hits[:4]))

# ── 6. names ──
section("names (stale refs, /as:<skill>, as:<agent>)")
TEXT_FILES = [p for base in (SKILLS, CODEX, AGENTS, ROOT / "README.md", ROOT / "ci", ROOT / "LICENSE")
              if base.exists()
              for p in ([base] if base.is_file() else base.rglob("*"))
              if p.is_file() and p.suffix in (".md", ".js", ".py", ".sh", ".json", "")
              and "__pycache__" not in p.parts
              and p.name != "validate.py"]   # this file quotes the patterns it forbids
for label, pat in STALE.items():
    hits = [f"{rel(p)}:{n}" for p in TEXT_FILES
            for n, line in enumerate(read(p).splitlines(), 1) if pat.search(line)]
    record(not hits, f"no stale {label}", " ".join(hits[:5]))
if NAME:
    skill_refs = [(rel(p), n, m.group(1)) for p in TEXT_FILES
                  for n, line in enumerate(read(p).splitlines(), 1)
                  for m in re.finditer(rf"/{re.escape(NAME)}:([A-Za-z0-9_-]+)", line)]
    bad = [f"{p}:{n} ({s})" for p, n, s in skill_refs if s not in sk]
    record(not bad, f"every /{NAME}:<skill> names a real skill", " ".join(bad[:5]))
    agent_refs = [(rel(p), n, m.group(1)) for p in TEXT_FILES
                  for n, line in enumerate(read(p).splitlines(), 1)
                  for m in re.finditer(rf"(?<![/\w]){re.escape(NAME)}:([A-Za-z0-9_-]+)", line)
                  if m.group(1) not in sk]
    bad = [f"{p}:{n} ({s})" for p, n, s in agent_refs if s not in agent_names]
    record(not bad, f"every {NAME}:<agent> names a real agent ({sorted(agent_names)})", " ".join(bad[:5]))

section("allowed-tools covers the body")
KNOWN_TOOLS = ["AskUserQuestion", "PushNotification", "ToolSearch", "TaskStop", "Monitor",
               "WebFetch", "WebSearch", "Workflow", "EnterWorktree", "NotebookEdit", "Skill"]
for d in skill_dirs(SKILLS):
    f = d / "SKILL.md"
    fm = frontmatter(read(f)) or {}
    allowed = fm.get("allowed-tools", "")
    if not allowed:
        record(True, f"skills/{d.name}: no allowed-tools (inherits session tools)")
        continue
    body = read(f).split("---", 2)[-1]
    missing = [t for t in KNOWN_TOOLS
               if re.search(rf"\b{t}\b", body) and t not in allowed
               and not re.search(rf"no {t}\b|without {t}\b", body, re.I)]
    record(not missing, f"skills/{d.name}: allowed-tools covers the body", ", ".join(missing))

# ── 7. codex packaging ──
section("codex packaging")
drift = []
for name in sorted(ck):
    for sub in ("references", "scripts", "roles"):
        sdir, cdir = SKILLS / name / sub, CODEX / name / sub
        # Drive from the source side so a MISSING Codex file fails, not just a changed one.
        if sdir.is_dir():
            for sf in sdir.rglob("*"):
                if sf.is_file() and "__pycache__" not in sf.parts:
                    cf = cdir / sf.relative_to(sdir)
                    if not cf.is_file():
                        drift.append(f"missing {rel(cf)}")
                    elif cf.read_bytes() != sf.read_bytes():
                        drift.append(f"differs {rel(cf)}")
        # ...and from the Codex side so a leftover file fails too.
        if cdir.is_dir():
            for cf in cdir.rglob("*"):
                if cf.is_file() and "__pycache__" not in cf.parts:
                    if not (sdir / cf.relative_to(cdir)).is_file():
                        drift.append(f"orphan {rel(cf)}")
record(not drift, "codex assets byte-identical to skills/ (run ci/build-codex.sh)", " ".join(drift[:5]))
leak = [str(rel(p)) for p in (ROOT / "skills-codex").rglob("workflows") if p.is_dir()]
record(not leak, "no workflows/ under skills-codex", " ".join(leak))
links = [str(rel(p)) for p in ROOT.rglob("*") if p.is_symlink() and ".git" not in p.parts]
record(not links, "no symlinks in the repo (plugin installers strip/refuse them)", " ".join(links[:5]))

# ── 8. syntax ──
section("syntax")
def collect(suffix):
    return sorted({p for base in (SKILLS, CODEX, AGENTS, ROOT / "ci") if base.exists()
                   for p in base.rglob(f"*{suffix}") if "__pycache__" not in p.parts})

for py in collect(".py"):
    try:
        compile(read(py), str(py), "exec")   # in-process: never writes __pycache__
        record(True, f"compiles {rel(py)}")
    except SyntaxError as e:
        record(False, f"compiles {rel(py)}", f"line {e.lineno}: {e.msg}")
WRAP = "async function __wf(args, parallel, agent, phase, log, budget, pipeline, workflow){\n"
for js in [p for p in collect(".js") if p.name.endswith(".workflow.js")]:
    src = read(js)
    body = re.sub(r"^export\s+", "", src, flags=re.M)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=True) as tmp:
        tmp.write(WRAP + body + "\n}\n")
        tmp.flush()
        r = subprocess.run(["node", "--check", tmp.name], capture_output=True, text=True)
    record(r.returncode == 0, f"node --check {rel(js)}", first_error(r.stderr) if r.returncode else "")
    record("import(" not in src and "Date.now(" not in src and "Math.random(" not in src,
           f"{rel(js)} has no import()/Date.now()/Math.random()")
for sh in collect(".sh"):
    r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
    record(r.returncode == 0, f"bash -n {rel(sh)}", r.stderr.strip() if r.returncode else "")

print("\n" + "=" * 48)
MIN_CHECKS = 60   # bump when checks are added; a silent drop means one stopped running
if checks < MIN_CHECKS:
    print(f"FAILED — only {checks} checks ran, expected at least {MIN_CHECKS} "
          f"(a check was removed or silently skipped)")
    sys.exit(1)
if failures:
    print(f"FAILED — {len(failures)}/{checks} checks failed:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"OK — all {checks} checks passed.")
