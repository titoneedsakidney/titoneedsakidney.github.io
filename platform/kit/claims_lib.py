#!/usr/bin/env python3
"""Claims on backlog items: git-tag leases, so two workers never pick the same rebuild item.

Same protocol as the Home Ops worker claims: one annotated tag per claimed item on origin,
`claim/backlog/<item-id>`, whose message is one line of JSON {worker, claimed_at, expires_at, ...}.
  - Creating the tag is atomic: a push of an existing tag name is rejected, so exactly one racing worker wins.
  - An expired claim is taken over with `--force-with-lease` against the exact old tag object, so two racing
    takeovers cannot both win either.
  - Only the holder can release or renew (the owner may force a release).
Standard library and the `git` CLI only. Nothing here changes the backlog file: a claim is a lock, not a status.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PREFIX = "refs/tags/claim/backlog/"
# The same claim, mirrored as a branch with ONE name for every kind of worker. Workers that cannot push tags (the GitHub connector) claim
# by creating this branch; branch creation is atomic, and per-kind work branches (chatgpt/x, codex/x) are not (found by trial test E1).
MIRROR = "refs/heads/claims/"
SCHEMA = "backlog-claim-v1"
DEFAULT_TTL_HOURS = 24
MAX_TTL_HOURS = 72


class ClaimError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


def _git(repo: Path, *args: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise ClaimError("GIT_FAILED", (result.stderr or result.stdout).strip().splitlines()[-1] if (result.stderr or result.stdout).strip() else "git failed")
    return result


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _decode(ref: str, oid: str, subject: str, now: datetime) -> dict | None:
    try:
        payload = json.loads(subject)
        expires = _parse_time(payload["expires_at"])
        if expires.tzinfo is None or expires.utcoffset() is None:
            return None
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if payload.get("schema") != SCHEMA or not isinstance(payload.get("worker"), str):
        return None
    return {**payload, "item": ref[len(PREFIX):], "tag_oid": oid, "expired": expires <= now}


def _read(repo: Path, remote: str, now: datetime) -> tuple[dict[str, dict], dict[str, str]]:
    """(valid claims by item, oid of malformed claim tags by item)."""
    _git(repo, "fetch", "--prune", "--quiet", remote, f"+{PREFIX}*:{PREFIX}*", timeout=60)
    out = _git(repo, "for-each-ref", "--format=%(refname)%09%(objectname)%09%(contents:subject)", PREFIX[:-1]).stdout
    claims, malformed = {}, {}
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        found = _decode(parts[0], parts[1], parts[2], now)
        if found:
            claims[found["item"]] = found
        else:
            malformed[parts[0][len(PREFIX):]] = parts[1]
    return claims, malformed


def fetch_claims(repo: Path, remote: str = "origin", now: datetime | None = None) -> dict[str, dict]:
    """Current claims on the remote, keyed by item id. Malformed tags are ignored (never treated as a lock)."""
    return _read(repo, remote, now or datetime.now(timezone.utc))[0]


def _make_tag(repo: Path, item: str, payload: dict) -> str:
    ref = PREFIX + item
    _git(repo, "tag", "-a", "-f", "-m", json.dumps(payload, separators=(",", ":")), ref[len("refs/tags/"):], "HEAD")
    return ref


def _payload(item: str, worker: str, ttl_hours: float, now: datetime, note: str | None, by: str | None) -> dict:
    if not 0 < ttl_hours <= MAX_TTL_HOURS:
        raise ClaimError("BAD_TTL", f"ttl must be between 0 and {MAX_TTL_HOURS} hours")
    payload = {"schema": SCHEMA, "item": item, "worker": worker, "claimed_at": _iso(now),
               "expires_at": _iso(now + timedelta(hours=ttl_hours))}
    if note:
        payload["note"] = note[:120]
    if by:
        payload["claimed_by"] = by
    return payload


def _mirror_exists(repo: Path, remote: str, item: str) -> bool:
    out = _git(repo, "ls-remote", "--heads", remote, MIRROR + item, check=False)
    return out.returncode == 0 and bool(out.stdout.strip())


def _claim_commit(repo: Path, item: str, worker: str) -> str:
    """A unique parentless commit on the empty tree. Pushing it to an existing claims/<item> is always rejected (not a fast-forward),
    even when that branch was created from the same main commit; pushing the same commit twice would silently succeed."""
    made = subprocess.run(["git", "hash-object", "-t", "tree", "-w", "--stdin"], cwd=repo, input="", capture_output=True, text=True, timeout=30, check=False)
    tree = made.stdout.strip() or "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # the empty tree
    done = subprocess.run(["git", "-c", "user.name=claim", "-c", "user.email=claim@invalid", "commit-tree", tree, "-m",
                           f"claim {item} by {worker} at {datetime.now(timezone.utc).isoformat()} #{time.time_ns()}"],
                          cwd=repo, capture_output=True, text=True, check=False)
    if done.returncode != 0 or not done.stdout.strip():
        raise ClaimError("NO_BASE", "cannot create the claim commit")
    return done.stdout.strip()


def claim(repo: Path, item: str, worker: str, *, ttl_hours: float = DEFAULT_TTL_HOURS, note: str | None = None,
          by: str | None = None, remote: str = "origin", now: datetime | None = None) -> dict:
    """Claim, renew (same worker) or take over an expired claim. Raises ClaimError CLAIM_HELD / CLAIM_LOST."""
    now = now or datetime.now(timezone.utc)
    claims, malformed = _read(repo, remote, now)
    existing = claims.get(item)
    if existing and not existing["expired"] and existing["worker"] != worker:
        raise ClaimError("CLAIM_HELD", f"{item} is held by {existing['worker']} until {existing['expires_at']}")
    payload = _payload(item, worker, ttl_hours, now, note, by)
    made_mirror = False
    if existing is None:
        # No tag claim. A branch claims/<item> that exists anyway was made by a worker that cannot push tags: it holds the item.
        if _mirror_exists(repo, remote, item):
            raise ClaimError("CLAIM_HELD", f"{item} is held through the shared claim branch claims/{item}")
        made = _git(repo, "push", "--quiet", remote, f"{_claim_commit(repo, item, worker)}:{MIRROR}{item}", check=False)
        if made.returncode != 0:
            raise ClaimError("CLAIM_LOST", f"another worker claimed {item} first (claims/{item})")
        made_mirror = True
    ref = _make_tag(repo, item, payload)
    replace_oid = existing["tag_oid"] if existing else malformed.get(item)
    if replace_oid:
        # The lease is the force authorization. A leading '+' on the refspec
        # bypasses it, letting a second expired-claim takeover overwrite the
        # first winner after both workers read the same old tag.
        push = _git(repo, "push", "--quiet", f"--force-with-lease={ref}:{replace_oid}", remote, f"{ref}:{ref}", check=False)
    else:
        push = _git(repo, "push", "--quiet", remote, f"{ref}:{ref}", check=False)
    if push.returncode != 0:
        _git(repo, "tag", "-d", ref[len("refs/tags/"):], check=False)
        if made_mirror:
            _git(repo, "push", "--quiet", remote, f":{MIRROR}{item}", check=False)
        raise ClaimError("CLAIM_LOST", f"another worker claimed {item} first")
    if existing is not None and not _mirror_exists(repo, remote, item):  # old claims made before the mirror existed
        _git(repo, "push", "--quiet", remote, f"{_claim_commit(repo, item, worker)}:{MIRROR}{item}", check=False)
    return {**payload, "renewed": bool(existing and existing["worker"] == worker), "took_over_expired": bool(existing and existing["expired"] and existing["worker"] != worker)}


def release(repo: Path, item: str, worker: str, *, force: bool = False, remote: str = "origin", now: datetime | None = None) -> dict:
    existing = fetch_claims(repo, remote, now).get(item)
    if existing is None:
        return {"item": item, "released": False, "reason": "no claim"}
    if existing["worker"] != worker and not force:
        raise ClaimError("NOT_HOLDER", f"{item} is held by {existing['worker']}, not {worker}")
    ref = PREFIX + item
    push = _git(repo, "push", "--quiet", f"--force-with-lease={ref}:{existing['tag_oid']}", remote, f":{ref}", check=False)
    _git(repo, "tag", "-d", ref[len("refs/tags/"):], check=False)
    if push.returncode != 0:
        raise ClaimError("CLAIM_LOST", f"{item} changed while releasing")
    _git(repo, "push", "--quiet", remote, f":{MIRROR}{item}", check=False)
    return {"item": item, "released": True, "worker": existing["worker"]}


def renew(repo: Path, item: str, worker: str, *, ttl_hours: float = DEFAULT_TTL_HOURS, remote: str = "origin", now: datetime | None = None) -> dict:
    existing = fetch_claims(repo, remote, now).get(item)
    if existing is None or existing["worker"] != worker:
        raise ClaimError("NOT_HOLDER", f"{worker} does not hold {item}")
    return claim(repo, item, worker, ttl_hours=ttl_hours, note=existing.get("note"), by=existing.get("claimed_by"), remote=remote, now=now)


def claims_from_github(api, owner: str, repo: str, now: datetime | None = None) -> dict[str, dict]:
    """The same claims read through the GitHub REST API (for the boards, which have no checkout). Best effort."""
    now = now or datetime.now(timezone.utc)
    prefix = PREFIX[len("refs/"):]
    out = {}
    for ref in api(f"repos/{owner}/{repo}/git/matching-refs/{prefix}") or []:
        obj = ref.get("object", {})
        if obj.get("type") != "tag":
            continue
        tag = api(f"repos/{owner}/{repo}/git/tags/{obj['sha']}")
        claim_ = _decode(ref["ref"], obj["sha"], (tag.get("message") or "").splitlines()[0] if tag.get("message") else "", now)
        if claim_:
            out[claim_["item"]] = claim_
    return out
