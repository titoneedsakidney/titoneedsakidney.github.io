#!/usr/bin/env python3
"""Question ledger: a question put to Tito in a chat he does not read must not wait there (Tito, 2026-11-18).

Three parts, one file, stdlib only, every hook path fails open:
  Stop hook            the reply just finished ends in a question -> one 'open' line in the ledger.
  UserPromptSubmit     the next turn in the same project sees the open questions and is told: answer it from the record if the record answers it
                       ('answer'), else put it in the Foyer ('card'). A typed answer from Tito also closes it ('answer').
  sweep (hourly timer) a question still open after --hours (default 6) becomes a Foyer card without anyone's help: a loop that stopped cannot strand it.

The record answers first (lead autonomy charter, docs/decisions/2026-11-25-lead-autonomy-charter.json, rule 1: a question the record answers is not
asked). Before a question becomes a card, the sweep looks it up in the decision records (status in force, the decision text and the charter answers)
and the standing facts; a clear match closes the question as answered by the record and the next turn in that project is shown the answer. A weaker
match rides along as a hint, on the prompt and in the card's `record_hint`.

Every ask carries a default and a date (charter q6): a card may say `default` (one of its options) and `default_on` (a date). When nobody has
answered by that date the sweep writes the default as the answer (<id>.answer.json, via 'default taken') and the asking project is told. A question
about money, sign-ins or access never gets a default (those stay Tito's; the words are a guard, not the rule).

The Foyer reads cards from ~/.local/state/portfolio-hub/foyer/session-questions/<id>.json (format below); the ledger is
~/.local/state/claude-hooks/questions.jsonl (events, newest line wins per id). Local, not in git.

  hook_question_ledger.py                  hook mode: JSON on stdin (hook_event_name Stop | UserPromptSubmit)
  hook_question_ledger.py list [--all]     open questions (or every id with its state)
  hook_question_ledger.py answer ID [--by self|tito|record] [--note TEXT]
  hook_question_ledger.py card ID [--option A --option B] [--default A] [--days N]   write the Foyer card now (default applies after N days, 7)
  hook_question_ledger.py lookup TEXT      what the record says about a question (JSON), nothing written
  hook_question_ledger.py sweep [--hours N]
Card file: {"schema":"session-question-v1","id","question","asked_at","project","session","why":"...","options":[optional, 2 to 5 answers the asker offers],
            "default": optional one of the options, "default_on": "YYYY-MM-DD", "record_hint": optional {"source","text"}}.
A reply that ends with a line 'Options: A | B | C' carries its answers into the card (the Foyer shows one button each); a line 'Default: A' names the
answer taken when nobody answers in 7 days.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
LEDGER = Path(os.environ.get("CLAUDE_QUESTION_LEDGER") or Path.home() / ".local" / "state" / "claude-hooks" / "questions.jsonl")
CARDS = Path(os.environ.get("CLAUDE_QUESTION_CARDS") or Path.home() / ".local" / "state" / "portfolio-hub" / "foyer" / "session-questions")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")
MAX_Q = 600
SHOW = 3
RECENT_DAYS = 3
DEFAULT_DAYS = 7
OPTIONS_LINE = re.compile(r"^\s*(?:\*\*)?(?:options|answers)(?:\*\*)?\s*:\s*(.+?)\s*$", re.I)
DEFAULT_LINE = re.compile(r"^\s*(?:\*\*)?default(?:\*\*)?\s*:\s*(.+?)\s*$", re.I)
# Words that mark the asks that stay Tito's (charter q5/q6): money, sign-ins, access. A guard on the default, never the rule.
NO_DEFAULT = re.compile(r"(\$\s?\d|\b(?:buy|buying|purchase|pay|paying|spend|price|cost|credential|password|passcode|sign[- ]?in|log[- ]?in|token|api key|grant access|private data|statement)s?\b)", re.I)
STOP_WORDS = set("""the a an and or of to in on for is it its this that these those with be we i you he she they do does did should shall would could can may
me my our your his her their as by at from into onto than then there here what which who whom whose when where why how all any both each few more most other
some such no nor not only own same so too very just also about above after again against before below between during further once over under until up down
out off while because if will am are was were been being have has had having want wants wanted need needs like still yet already ever never now today
please thanks ok okay yes one two three want""".split())


def now() -> float:
    return time.time()


def iso(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def split_options(text: str) -> tuple[str, list[str]]:
    """A reply may end with one line 'Options: A | B | C' (2 to 5 answers the asker offers, Tito 2026-11-24: "Super useful buttons"). Returns the text without that
    line and the options; ([] when there is no such line or it does not hold 2 to 5 different non-empty answers)."""
    lines = (text or "").rstrip().split("\n")
    if not lines:
        return text or "", []
    m = OPTIONS_LINE.match(lines[-1])
    if not m:
        return text or "", []
    opts = [o.strip(" *`_")[:90] for o in m.group(1).split("|")]
    opts = [o for o in opts if o]
    ok = 2 <= len(opts) <= 5 and len({o.lower() for o in opts}) == len(opts)
    return "\n".join(lines[:-1]), (opts if ok else [])


def split_trailer(text: str) -> tuple[str, list[str], str]:
    """The reply's trailing 'Options:' and 'Default:' lines, in either order: (text without them, options, default). The default counts only when it
    is one of the options (case-insensitive) and the question is not one of money, sign-in or access."""
    body, options, default = text or "", [], ""
    for _ in range(2):
        lines = body.rstrip().split("\n")
        if not lines:
            break
        m = DEFAULT_LINE.match(lines[-1])
        if m and not default:
            default = m.group(1).strip(" *`_")[:90]
            body = "\n".join(lines[:-1])
            continue
        rest, opts = split_options(body)
        if opts and not options:
            body, options = rest, opts
            continue
        break
    default = next((o for o in options if o.lower() == default.lower()), "") if options else ""
    if default and NO_DEFAULT.search(body):
        default = ""
    return body, options, default


def final_question(text: str) -> str:
    """The last prose paragraph of a reply when it ends in a question mark, else ''. Code blocks and inline code are ignored. Trailing 'Options:' and 'Default:' lines are not part of it."""
    text = split_trailer(text)[0]
    prose = INLINE.sub(" ", FENCE.sub(" ", text or "")).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", prose) if p.strip()]
    if not paras:
        return ""
    last = " ".join(paras[-1].split())
    return last[-MAX_Q:] if last.endswith("?") else ""


def qid(project: str, question: str) -> str:
    return hashlib.sha1(f"{project}\n{question}".encode()).hexdigest()[:12]


def rows() -> dict[str, dict]:
    """id -> newest row. A malformed line is skipped."""
    out: dict[str, dict] = {}
    try:
        for line in LEDGER.read_text(errors="ignore").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id"):
                out[r["id"]] = {**out.get(r["id"], {}), **r}
    except OSError:
        pass
    return out


def write(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def open_rows(project: str | None = None, within_days: float | None = None) -> list[dict]:
    cut = now() - within_days * 86400 if within_days else 0
    return sorted((r for r in rows().values() if r.get("state") == "open" and (project is None or r.get("project") == project) and r.get("at", 0) >= cut),
                  key=lambda r: r.get("at", 0))


# ---------------------------------------------------------------- the record answers first

def records_root(project: str | None = None) -> Path | None:
    """Where docs/decisions and docs/standing-facts.json are read from: $CLAUDE_RECORDS_ROOT, else the fullest of the project folder, the
    platform clone and the copy beside this kit (the installed hooks folder carries docs/). Whichever has the most decision records wins."""
    env = os.environ.get("CLAUDE_RECORDS_ROOT")
    if env:
        return Path(env)
    candidates = [Path(project)] if project else []
    candidates += [Path.home() / "work" / "automationpc-platform", HERE.parent]
    best, best_n = None, 0
    for c in candidates:
        try:
            n = sum(1 for _ in (c / "docs" / "decisions").glob("*.json"))
        except OSError:
            n = 0
        if n > best_n:
            best, best_n = c, n
    return best


def record_texts(root: Path) -> list[tuple[str, str]]:
    """(source, text) for every in-force decision (its decision line and each charter answer) and every standing fact."""
    out: list[tuple[str, str]] = []
    for p in sorted((root / "docs" / "decisions").glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(rec, dict) or rec.get("status") != "in force":
            continue
        rid = str(rec.get("id") or p.stem)
        if isinstance(rec.get("decision"), str):
            out.append((f"record {rid}", rec["decision"]))
        charter = rec.get("charter")
        if isinstance(charter, dict):
            for key, row in charter.items():
                if isinstance(row, dict) and isinstance(row.get("answer"), str):
                    out.append((f"record {rid} {key}", row["answer"]))
    try:
        facts = json.loads((root / "docs" / "standing-facts.json").read_text(encoding="utf-8")).get("facts", [])
    except (OSError, ValueError, AttributeError):
        facts = []
    for f in facts:
        if isinstance(f, dict) and isinstance(f.get("statement"), str):
            out.append((f"fact {f.get('id', '?')}", f["statement"]))
    return out


def stem(w: str) -> str:
    """Crude: merged/merges/merging/merge count as one word. Enough for overlap counting, never for meaning."""
    for end in ("ing", "ies", "ed", "es", "s"):
        if w.endswith(end) and len(w) - len(end) >= 4:
            w = w[: -len(end)] + ("y" if end == "ies" else "")
            break
    return w[:-1] if w.endswith("e") and len(w) > 4 else w


def words(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z][a-z0-9-]{3,}", (text or "").lower()) if w not in STOP_WORDS}


def record_answer(question: str, root: Path | None) -> dict | None:
    """The record text that shares the most content words with the question: {"source", "text", "shared", "ratio", "strength"}; strength is
    'strong' (the record answers it) or 'hint' (worth a look). None for a short question or no overlap worth showing. Word overlap is a guess,
    never a judgment: a strong match is still shown to the asking chat, which can card it after all."""
    q = words(question)
    if len(q) < 4 or root is None:
        return None
    best = None
    for source, text in record_texts(root):
        shared = q & words(text)
        ratio = len(shared) / len(q)
        if best is None or (len(shared), ratio) > (best["shared"], best["ratio"]):
            best = {"source": source, "text": text[:400], "shared": len(shared), "ratio": round(ratio, 2)}
    if not best:
        return None
    if best["shared"] >= 5 and best["ratio"] >= 0.5:
        return {**best, "strength": "strong"}
    if best["shared"] >= 3 and best["ratio"] >= 0.3:
        return {**best, "strength": "hint"}
    return None


# ---------------------------------------------------------------- cards

def card(row: dict, why: str) -> Path:
    CARDS.mkdir(parents=True, exist_ok=True)
    p = CARDS / f"{row['id']}.json"
    data = {"schema": "session-question-v1", "id": row["id"], "question": row["question"], "asked_at": iso(row["at"]),
            "project": row.get("project", ""), "session": row.get("session", ""), "why": why}
    if row.get("options"):
        data["options"] = row["options"]   # the asker's own answers: the Foyer shows one button each
        if row.get("default") in row["options"] and not NO_DEFAULT.search(row.get("question", "")):
            data["default"] = row["default"]
            days = row.get("default_days") or DEFAULT_DAYS
            data["default_on"] = (dt.datetime.fromtimestamp(row["at"], dt.timezone.utc) + dt.timedelta(days=days)).strftime("%Y-%m-%d")
    hint = row.get("record_hint")
    if isinstance(hint, dict) and hint.get("text"):
        data["record_hint"] = {"source": hint.get("source", ""), "text": hint["text"][:400]}
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    write({**row, "state": "carded", "carded_at": now()})
    return p


def on_stop(call: dict) -> None:
    from hook_stop_wording_lint import last_assistant_text
    reply = last_assistant_text(call.get("transcript_path"))
    q = final_question(reply)
    if not q:
        return
    _, options, default = split_trailer(reply)
    project = str(call.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or "")
    i = qid(project, q)
    if rows().get(i, {}).get("state") in ("open", "carded"):
        return
    extra = {}
    if options:
        extra["options"] = options
        if default:
            extra["default"] = default
    write({"id": i, "state": "open", "at": now(), "project": project, "session": str(call.get("session_id") or ""), "question": q, **extra})


def archive(i: str) -> None:
    """Move a closed question's card and answer files to CARDS/archive/ so the Foyer drops the card and the folder does not grow."""
    arc = CARDS / "archive"
    for suffix in (".json", ".answer.json"):
        try:
            arc.mkdir(parents=True, exist_ok=True)
            (CARDS / f"{i}{suffix}").replace(arc / f"{i}{suffix}")
        except OSError:
            pass


def take_defaults(on: str | None = None) -> list[str]:
    """Every card (whoever wrote it) whose default_on has come with nobody answering gets its default as the answer: <id>.answer.json with via
    'default taken'. A money, sign-in or access question is skipped even when a default was written on it. Returns the ids taken."""
    on = on or today()
    taken = []
    try:
        names = sorted(os.listdir(CARDS))
    except OSError:
        return taken
    for name in names:
        if not name.endswith(".json") or name.endswith(".answer.json"):
            continue
        i = name[: -len(".json")]
        try:
            data = json.loads((CARDS / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not data.get("default") or not isinstance(data.get("default_on"), str):
            continue
        if data["default_on"] > on or (CARDS / f"{i}.answer.json").exists() or NO_DEFAULT.search(str(data.get("question", ""))):
            continue
        answer = {"answer": str(data["default"]), "answered_at": iso(now()), "via": "default taken",
                  "note": f"nobody answered by {data['default_on']}; the default applies (lead autonomy charter q6); Tito's later answer replaces it"}
        tmp = CARDS / f".{i}.answer.tmp"
        tmp.write_text(json.dumps(answer, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(CARDS / f"{i}.answer.json")
        taken.append(i)
    return taken


def take_answers(project: str | None) -> list[tuple[dict, str, str]]:
    """Questions (of this project, or all when project is None) answered in the Foyer (<id>.answer.json beside the card), by Tito or by the
    default on its date: closed here, files archived, handed to the run once as (row, text, via)."""
    got = []
    for r in rows().values():
        if (project is not None and r.get("project") != project) or r.get("state") not in ("open", "carded"):
            continue
        try:
            a = json.loads((CARDS / f"{r['id']}.answer.json").read_text())
            text = str(a.get("answer", "")).strip()
            via = str(a.get("via", "") or "foyer")
        except (OSError, ValueError, AttributeError):
            continue
        if text:
            by = "default" if via == "default taken" else "tito"
            write({**r, "state": "answered", "answered_at": now(), "by": by, "note": text[:300]})
            archive(r["id"])
            got.append((r, text[:1000], via))
    return got


def take_record_answers(project: str | None, root: Path | None) -> list[tuple[dict, dict]]:
    """Open questions the record answers strongly: closed as answered by the record (no card), handed back as (row, match) so the asking
    project is told once. Only questions still 'open' (not yet carded) are closed this way."""
    got = []
    for r in open_rows(project):
        m = record_answer(r.get("question", ""), root)
        if m and m["strength"] == "strong":
            write({**r, "state": "answered", "answered_at": now(), "by": "record", "note": f"{m['source']}: {m['text'][:220]}", "shown": False})
            got.append((r, m))
    return got


def on_prompt(call: dict) -> None:
    project = str(call.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or "")
    for r, text, via in take_answers(project):
        if via == "default taken":
            print(f"Nobody answered your question [{r['id']}] by its date, so its default applies (charter q6): {text}. Question: {r['question']} Tito's later answer replaces it.")
        else:
            print(f"Tito answered your question [{r['id']}] in the Foyer. Question: {r['question']} Answer: {text}")
    me = Path(__file__).resolve()
    for r in rows().values():
        if r.get("project") == project and r.get("by") == "record" and r.get("shown") is False:
            write({**r, "shown": True})
            print(f"The record answered your question [{r['id']}], so it did not go to Tito. Question: {r['question']} Record: {r.get('note', '')} "
                  f"If the record does not answer it after all, run: python3 {me} card {r['id']} --option 'first answer' --option 'second answer'")
    mine = [r for r in open_rows(project, RECENT_DAYS)][-SHOW:]
    if not mine:
        return
    root = records_root(project)
    print("Open questions this project put to Tito that nobody has answered (a chat he does not read cannot hold them):")
    for r in mine:
        m = record_answer(r.get("question", ""), root)
        hint = f" The record may answer it ({m['source']}): {m['text'][:240]}" if m else ""
        print(f"- [{r['id']}] ({iso(r['at'])}) {r['question']}{hint}")
    print("If the message you were just given answers one, or the record does (docs/decisions, docs/standing-facts.json, the repo), act on it and run: "
          f"python3 {me} answer ID --by self|tito|record. If nothing clear answers it, run: python3 {me} card ID --option 'first answer' --option 'second answer' --default 'first answer' "
          "(2 to 5 answers Tito can tap; the default applies by itself after 7 days; it goes to the Foyer as a card). Do not ask it again in this chat. "
          "When you end a reply with a question for Tito, add two last lines: Options: first answer | second answer | third answer  and  Default: first answer")


def cmd_answer(a) -> int:
    r = rows().get(a.id)
    if not r:
        print("unknown id", file=sys.stderr)
        return 1
    write({**r, "state": "answered", "answered_at": now(), "by": a.by, "note": (a.note or "")[:300]})
    archive(a.id)
    return 0


def cmd_card(a) -> int:
    r = rows().get(a.id)
    if not r:
        print("unknown id", file=sys.stderr)
        return 1
    if a.option:
        r = {**r, "options": [o.strip()[:90] for o in a.option if o.strip()][:5]}
        if len(r["options"]) < 2 or len({o.lower() for o in r["options"]}) != len(r["options"]):
            r.pop("options")
    if a.default:
        r = {**r, "default": a.default.strip()[:90], "default_days": a.days}
    m = record_answer(r.get("question", ""), records_root(r.get("project")))
    if m:
        r = {**r, "record_hint": {"source": m["source"], "text": m["text"]}}
    print(card(r, "No clear answer in the record; asked in a chat Tito does not read."))
    return 0


def cmd_lookup(a) -> int:
    print(json.dumps(record_answer(" ".join(a.text), records_root(os.getcwd())), indent=1, ensure_ascii=False))
    return 0


def cmd_sweep(a) -> int:
    defaults = take_defaults()
    closed = take_answers(None)   # answered in the Foyer or by a default, project chat gone or not: close and archive, keep the text in the ledger note
    root = records_root()
    by_record = take_record_answers(None, root)
    n = 0
    for r in open_rows():
        if now() - r["at"] >= a.hours * 3600:
            m = record_answer(r.get("question", ""), root)
            if m:
                r = {**r, "record_hint": {"source": m["source"], "text": m["text"]}}
            card(r, f"Still open after {a.hours:g} hours; asked in a chat Tito does not read.")
            n += 1
    print(json.dumps({"carded": n, "answered": len(closed), "by_record": len(by_record), "defaults_taken": len(defaults)}))
    return 0


def cmd_list(a) -> int:
    for r in (sorted(rows().values(), key=lambda r: r.get("at", 0)) if a.all else open_rows()):
        print(f"{r['id']} {r.get('state'):9} {iso(r.get('at', 0))} {r.get('question', '')[:110]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("answer"); p.add_argument("id"); p.add_argument("--by", default="self", choices=("self", "tito", "record")); p.add_argument("--note")
    p = sub.add_parser("card"); p.add_argument("id"); p.add_argument("--option", action="append", help="one answer Tito can tap (give 2 to 5)")
    p.add_argument("--default", help="the option taken when nobody answers in --days days"); p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p = sub.add_parser("lookup"); p.add_argument("text", nargs="+")
    p = sub.add_parser("sweep"); p.add_argument("--hours", type=float, default=6)
    p = sub.add_parser("list"); p.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd:
        return {"answer": cmd_answer, "card": cmd_card, "lookup": cmd_lookup, "sweep": cmd_sweep, "list": cmd_list}[a.cmd](a)
    try:   # hook mode: never block, never raise
        call = json.loads(sys.stdin.read() or "{}")
        event = call.get("hook_event_name")
        if event == "Stop":
            on_stop(call)
        elif event == "UserPromptSubmit":
            on_prompt(call)
    except Exception:  # noqa: BLE001  (a hook must fail open)
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
