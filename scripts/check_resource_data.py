#!/usr/bin/env python3
"""Fail-closed validation for public, source-verified kidney resource placements.

Pure stdlib functions; no network access or implied verification of any URL.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from urllib.parse import urlsplit

ID = re.compile(r"^[a-z][a-z0-9-]{2,79}$")
LANGUAGES = {"en", "es"}
STATUSES = {"verified", "excluded"}
ORG_FIELDS = {"organization_id", "name", "official_url"}
PLACE_FIELDS = {
    "placement_id", "organization_id", "need", "destination_url",
    "destination_language", "geography", "verified_at", "source_url", "status",
}
PRIVATE_FIELDS = {
    "email", "phone", "contact", "contact_name", "contact_email", "mailbox",
    "recipient", "crm_id", "gmail_id", "person_id", "private_notes", "correspondence",
    "endorsement", "partner", "partnership", "approved_by",
}
FORBIDDEN_CLAIMS = re.compile(r"\b(endorse[sd]?|official partner|partnered with|"
                              r"affiliated with|sponsor(?:ed|ship)?|recommended by)\b", re.I)


def _url(value: object) -> bool:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return False
    try:
        u = urlsplit(value)
        return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password \
            and not u.fragment and u.port != 0
    except ValueError:
        return False


def _date(value: object) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        return date.fromisoformat(value) <= date.today()
    except ValueError:
        return False


def _private_fields(value: object, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in PRIVATE_FIELDS:
                errors.append(f"{location}.{key}: private or unsupported claim field")
            _private_fields(child, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _private_fields(child, f"{location}[{index}]", errors)


def validate(data: object) -> list[str]:
    """Return deterministic errors; empty list means structurally publishable, not source-verified."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root: expected object"]
    _private_fields(data, "root", errors)
    if data.get("schema") != "kidney-resource-placements-v1":
        errors.append("schema: expected kidney-resource-placements-v1")
    orgs, places = data.get("organizations"), data.get("placements")
    if not isinstance(orgs, list) or not isinstance(places, list):
        return errors + ["organizations and placements must be arrays"]
    seen_orgs: set[str] = set()
    for n, org in enumerate(orgs):
        loc = f"organizations[{n}]"
        if not isinstance(org, dict):
            errors.append(f"{loc}: expected object")
            continue
        if set(org) != ORG_FIELDS:
            errors.append(f"{loc}: expected fields {sorted(ORG_FIELDS)}")
        oid = org.get("organization_id")
        if not isinstance(oid, str) or not ID.fullmatch(oid):
            errors.append(f"{loc}: invalid organization_id")
        elif oid in seen_orgs:
            errors.append(f"{loc}: duplicate organization_id {oid}")
        else:
            seen_orgs.add(oid)
        if not _url(org.get("official_url")):
            errors.append(f"{loc}: official_url must be a clean HTTPS URL")
        name = org.get("name")
        if not isinstance(name, str) or not name.strip() or FORBIDDEN_CLAIMS.search(name):
            errors.append(f"{loc}: invalid or unsupported name")
    seen_places: set[str] = set()
    for n, place in enumerate(places):
        loc = f"placements[{n}]"
        if not isinstance(place, dict):
            errors.append(f"{loc}: expected object")
            continue
        if set(place) != PLACE_FIELDS:
            errors.append(f"{loc}: expected fields {sorted(PLACE_FIELDS)}")
        pid = place.get("placement_id")
        if not isinstance(pid, str) or not ID.fullmatch(pid):
            errors.append(f"{loc}: invalid placement_id")
        elif pid in seen_places:
            errors.append(f"{loc}: duplicate placement_id {pid}")
        else:
            seen_places.add(pid)
        if place.get("organization_id") not in seen_orgs:
            errors.append(f"{loc}: unknown organization_id")
        for field in ("need", "geography"):
            value = place.get(field)
            if not isinstance(value, str) or not value.strip() or FORBIDDEN_CLAIMS.search(value):
                errors.append(f"{loc}: invalid {field} or unsupported claim")
        if place.get("destination_language") not in LANGUAGES:
            errors.append(f"{loc}: destination_language must be en or es")
        if place.get("status") not in STATUSES:
            errors.append(f"{loc}: status must be verified or excluded")
        if not _date(place.get("verified_at")):
            errors.append(f"{loc}: verified_at must be a real, nonfuture YYYY-MM-DD date")
        for field in ("source_url", "destination_url"):
            if not _url(place.get(field)):
                errors.append(f"{loc}: {field} must be a clean HTTPS URL")
    return errors


def publishable(data: object) -> list[dict]:
    """Return only structurally valid, explicitly verified placements."""
    errors = validate(data)
    if errors:
        raise ValueError("; ".join(errors))
    return [row for row in data["placements"] if row["status"] == "verified"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", help="Public placements JSON file to check")
    args = parser.parse_args()
    try:
        with open(args.json_file, encoding="utf-8") as stream:
            data = json.load(stream)
        errors = validate(data)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
