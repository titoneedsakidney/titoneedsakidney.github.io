#!/usr/bin/env python3
"""Stdlib-only validator for the host executor contract.

Validates executor JSON documents against the schemas in this directory, plus the
recipe invariants that JSON Schema cannot express. No third-party packages, so any
repo's CI (or the executor itself) can run it:

    python3 executor/contract/validate.py recipe platform/deploy-recipe.json
    python3 executor/contract/validate.py recipe platform/deploy-recipe.json --host host.json
    python3 executor/contract/validate.py request  request.json
    python3 executor/contract/validate.py response response.json
    python3 executor/contract/validate.py protected protected.json
    python3 executor/contract/validate.py host host.json
    python3 executor/contract/validate.py unit my.service --namespace home-ops --host host.json --protected protected.json

Exit 0 and print OK, or exit 1 and print one error per line.

Supported JSON Schema subset (the schemas must use only these keywords):
type, properties, required, additionalProperties, enum, const, pattern, minLength,
maxLength, minimum, maximum, items, minItems, maxItems, uniqueItems, maxProperties,
oneOf, if/then/else, $ref (local #/$defs/...), $defs, $schema, $id, title, description.
"""
from __future__ import annotations

import fnmatch
import json
import posixpath
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMAS = {
    "request": "request.schema.json",
    "response": "response.schema.json",
    "recipe": "deploy-recipe.schema.json",
    "protected": "protected-set.schema.json",
    "host": "host-config.schema.json",
}
SUPPORTED = {
    "type", "properties", "required", "additionalProperties", "enum", "const", "pattern",
    "minLength", "maxLength", "minimum", "maximum", "items", "minItems", "maxItems",
    "uniqueItems", "maxProperties", "oneOf", "if", "then", "else", "$ref", "$defs", "$schema", "$id", "title",
    "description",
}
HA_ALLOWED = re.compile(r"(scripts\.yaml|scenes\.yaml|(dashboards|packages|themes)/[a-z][a-z0-9_-]{0,63}\.yaml)\Z")
HOST_TARGET = re.compile(r"(lib|share|unit):([A-Za-z0-9_][A-Za-z0-9._-]*(?:/[A-Za-z0-9_][A-Za-z0-9._-]*)*)\Z")
UNIT_SUFFIX = re.compile(r"\.(service|timer)\Z")
GROUP_NAME = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
UNIT_ALLOW = {
    "Unit": {"Description", "Documentation", "After", "Before", "Wants", "Requires", "BindsTo", "PartOf",
             "OnFailure", "StartLimitIntervalSec", "StartLimitBurst", "ConditionPathExists"},
    "Service": {"Type", "User", "Group", "WorkingDirectory", "ExecStart", "ExecStartPre", "ExecStartPost",
                "ExecStop", "ExecStopPost", "Environment", "Nice", "IOSchedulingClass", "Restart", "RestartSec", "TimeoutStartSec", "TimeoutStopSec",
                "RuntimeMaxSec", "RemainAfterExit", "StateDirectory", "CacheDirectory", "LogsDirectory",
                "ReadWritePaths", "ReadOnlyPaths", "NoNewPrivileges", "PrivateTmp", "PrivateDevices",
                "ProtectSystem", "ProtectHome", "ProtectKernelTunables", "ProtectKernelModules",
                "ProtectControlGroups", "RestrictSUIDSGID", "LockPersonality", "UMask", "MemoryMax", "CPUQuota",
                # Restriction-only hardening (signal-ops adoption gap G2): each one can only take capabilities away.
                "ProtectClock", "ProtectHostname", "RestrictAddressFamilies", "IPAddressDeny", "IPAddressAllow",
                # Credentials a service reads at start, only from the namespace's own data directory (checked below).
                # Owner 2026-10-07: "executor services may read credentials from /srv/data/<repo>/".
                "EnvironmentFile"},
    "Timer": {"OnCalendar", "OnBootSec", "OnActiveSec", "OnUnitActiveSec", "Persistent", "RandomizedDelaySec",
              "AccuracySec", "Unit"},
    "Install": {"WantedBy"},
}
UNIT_SECTIONS = {"service": ("Unit", "Service", "Install"), "timer": ("Unit", "Timer", "Install")}
UNIT_RELATIONS = {"After", "Before", "Wants", "Requires", "BindsTo", "PartOf", "OnFailure", "WantedBy", "Unit"}
SYSTEM_TARGETS = {"network-online.target", "network.target", "time-sync.target", "multi-user.target", "timers.target"}
# Ordering only (After= never starts anything): units outside the namespace a unit may wait for.
AFTER_ONLY = {"docker.service", "NetworkManager.service"}
NM_ROOT = "/etc/NetworkManager/conf.d"
SERVICE_TYPES = {"simple", "exec", "oneshot", "notify"}
TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: type(v) is int,
    "number": lambda v: type(v) in (int, float),
    "boolean": lambda v: type(v) is bool,
    "null": lambda v: v is None,
}


def load_schema(kind: str) -> dict:
    return json.loads((HERE / SCHEMAS[kind]).read_text(encoding="utf-8"))


def unsupported_keywords(schema: Any, path: str = "#") -> list[str]:
    """Return schema keywords outside the supported subset (property names excluded)."""
    found: list[str] = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key not in SUPPORTED:
                found.append(f"{path}/{key}")
            if key in ("properties", "$defs"):
                for name, sub in value.items():
                    found += unsupported_keywords(sub, f"{path}/{key}/{name}")
            elif key in ("items", "additionalProperties") and isinstance(value, dict):
                found += unsupported_keywords(value, f"{path}/{key}")
            elif key == "oneOf":
                for i, sub in enumerate(value):
                    found += unsupported_keywords(sub, f"{path}/oneOf/{i}")
            elif key in ("if", "then", "else") and isinstance(value, dict):
                found += unsupported_keywords(value, f"{path}/{key}")
    return found


def _resolve(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref supported: {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def ecma_anchors(pattern: str) -> str:
    """JSON Schema patterns are ECMA-262: a trailing '$' matches only at the very end. Python's '$' also
    matches before a final newline, so 'name\\n' would pass; use '\\Z' instead."""
    if pattern.endswith("$") and not pattern.endswith("\\$"):
        return pattern[:-1] + r"\Z"
    return pattern


def errors(value: Any, schema: dict, root: dict | None = None, at: str = "$") -> list[str]:
    root = root if root is not None else schema
    if "$ref" in schema:
        return errors(value, _resolve(root, schema["$ref"]), root, at)
    out: list[str] = []
    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(TYPES[t](value) for t in allowed):
            return [f"{at}: expected {'/'.join(allowed)}"]
    if "const" in schema and value != schema["const"]:
        out.append(f"{at}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{at}: must be one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            out.append(f"{at}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(f"{at}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(ecma_anchors(schema["pattern"]), value):
            out.append(f"{at}: does not match {schema['pattern']}")
    if type(value) in (int, float) and type(value) is not bool:
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{at}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{at}: above {schema['maximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(f"{at}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{at}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True) for v in value]
            if len(seen) != len(set(seen)):
                out.append(f"{at}: items are not unique")
        if "items" in schema:
            for i, item in enumerate(value):
                out += errors(item, schema["items"], root, f"{at}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                out.append(f"{at}: missing {name}")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            out.append(f"{at}: more than {schema['maxProperties']} properties")
        extra = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name in props:
                out += errors(item, props[name], root, f"{at}.{name}")
            elif extra is False:
                out.append(f"{at}: unexpected property {name}")
            elif isinstance(extra, dict):
                out += errors(item, extra, root, f"{at}.{name}")
    if "oneOf" in schema:
        results = [errors(value, sub, root, at) for sub in schema["oneOf"]]
        matches = [r for r in results if not r]
        if len(matches) != 1:
            if not matches:
                best = min(results, key=len)
                out.append(f"{at}: matches no oneOf branch (closest: {'; '.join(best[:3])})")
            else:
                out.append(f"{at}: matches {len(matches)} oneOf branches, expected exactly 1")
    if "if" in schema:  # `if` only picks the branch; its own errors are never reported
        branch = schema.get("then") if not errors(value, schema["if"], root, at) else schema.get("else")
        if branch:
            out += errors(value, branch, root, at)
    return out


def in_namespace(name: str, ns: str) -> bool:
    """A systemd unit, container or other host name belongs to ns only if it is ns or starts with ns + '-'.
    Safe because host_invariants requires the namespace set to be prefix-free."""
    return name == ns or name.startswith(ns + "-")


def host_target_problem(target: str, ns: str) -> str | None:
    """A lib:/share:/unit: target must sit inside the namespace: the first path component (or, for unit:, the
    single file name without its suffix) is the namespace or starts with '<ns>-'."""
    m = HOST_TARGET.match(target)
    if not m:
        return "is not a lib:/share:/unit: target"
    alias, rel = m.groups()
    if ".." in rel.split("/"):
        return "contains '..'"
    if alias == "unit":
        if "/" in rel or not UNIT_SUFFIX.search(rel):
            return "unit: targets are single .service or .timer file names"
        return None if in_namespace(UNIT_SUFFIX.sub("", rel), ns) else f"is outside namespace {ns}"
    if len(rel.split("/")) != 2:
        return "must be '<directory>/<file>' (exactly two path components)"
    return None if in_namespace(rel.split("/")[0], ns) else f"is outside namespace {ns}"


def recipe_invariants(recipe: dict, gated: frozenset = frozenset()) -> list[str]:
    """Rules the schema cannot express. The executor enforces the same rules at release time."""
    out: list[str] = []
    ids: set[str] = set()
    targets: set[str] = set()
    ns = recipe.get("namespace", "")
    for unit in recipe.get("units", []):
        uid = unit.get("id")
        if uid in ids:
            out.append(f"unit {uid}: duplicate id")
        ids.add(uid)
        kind = unit.get("kind")
        for f in unit.get("files", []):
            target = f.get("target", "")
            if target in targets:
                out.append(f"unit {uid}: target {target} is claimed twice")
            targets.add(target)
            if kind == "host_files":
                problem = host_target_problem(target, ns)
                if problem:
                    out.append(f"unit {uid}: {target} {problem}")
                if f.get("mode") == "0755" and target.startswith("unit:"):
                    out.append(f"unit {uid}: {target} unit files are always 0644")
            elif kind == "grafana_dashboard":
                if not target.startswith("grafana:"):
                    out.append(f"unit {uid}: {target} must be a grafana:<uid> target")
            elif not (HA_ALLOWED.match(target.partition(":")[2]) or target in gated):
                out.append(f"unit {uid}: {target} is outside the HA YAML boundary")
            elif target in gated and (len(unit.get("files", [])) != 1 or (unit.get("activate") or {}).get("ha") != "restart"):
                out.append(f"unit {uid}: a unit for {target} has exactly one file and activates with an HA restart")
        if kind == "host_files":
            out += host_unit_invariants(unit, ns)
        elif kind == "app_release":
            out += app_unit_invariants(unit, ns)
        elif kind == "grafana_dashboard":
            for check in unit.get("smoke", []):
                if check.get("kind") in ("ha_config_check", "unit_state"):
                    out.append(f"unit {uid}: {check.get('kind')} smoke checks do not apply to grafana_dashboard units")
        elif kind == "mqtt_accounts":
            if not any(fnmatch.fnmatchcase(unit.get("accounts_file", ""), g) for g in unit.get("watch", [])):
                out.append(f"unit {uid}: accounts_file must match one of its watch globs (a change to it must select the unit)")
            for check in unit.get("smoke", []):
                if check.get("kind") in ("ha_config_check", "unit_state"):
                    out.append(f"unit {uid}: {check.get('kind')} smoke checks do not apply to mqtt_accounts units")
        elif kind == "pg_roles":
            if not any(fnmatch.fnmatchcase(unit.get("roles_file", ""), g) for g in unit.get("watch", [])):
                out.append(f"unit {uid}: roles_file must match one of its watch globs (a change to it must select the unit)")
            for check in unit.get("smoke", []):
                if check.get("kind") in ("ha_config_check", "unit_state"):
                    out.append(f"unit {uid}: {check.get('kind')} smoke checks do not apply to pg_roles units")
        elif kind == "python_venv":
            if not any(fnmatch.fnmatchcase(unit.get("lock_file", ""), g) for g in unit.get("watch", [])):
                out.append(f"unit {uid}: lock_file must match one of its watch globs (a change to it must select the unit)")
            for check in unit.get("smoke", []):
                if check.get("kind") in ("ha_config_check", "unit_state"):
                    out.append(f"unit {uid}: {check.get('kind')} smoke checks do not apply to python_venv units")
        elif kind == "git_checkout":
            for check in unit.get("smoke", []):
                if check.get("kind") == "ha_config_check":
                    out.append(f"unit {uid}: ha_config_check belongs to ha_yaml units")
                elif check.get("kind") == "unit_state" and not in_namespace(UNIT_SUFFIX.sub("", check.get("name", "")), ns):
                    out.append(f"unit {uid}: smoke unit {check.get('name')} is outside namespace {ns}")
        else:
            for check in unit.get("smoke", []):
                if check.get("kind") == "unit_state":
                    out.append(f"unit {uid}: unit_state smoke checks belong to host_files units")
        if kind != "host_files":
            for check in unit.get("smoke", []):
                if check.get("kind") == "file_fresh":
                    out.append(f"unit {uid}: file_fresh smoke checks belong to host_files units")
    return out


def app_unit_invariants(unit: dict, ns: str) -> list[str]:
    """app_release: the pointer unit is a .service in the namespace, it is the service that gets restarted, include globs
    stay relative, and smoke checks are host checks."""
    uid, out = unit.get("id"), []
    target = (unit.get("unit") or {}).get("target", "")
    problem = host_target_problem(target, ns)
    if problem:
        out.append(f"unit {uid}: {target} {problem}")
    elif not target.endswith(".service"):
        out.append(f"unit {uid}: the pointer unit {target} must be a .service")
    service = (unit.get("activate") or {}).get("service", "")
    if target.partition(":")[2] != service:
        out.append(f"unit {uid}: activate.service {service} must be the pointer unit {target.partition(':')[2]}")
    if not in_namespace(UNIT_SUFFIX.sub("", service), ns):
        out.append(f"unit {uid}: service {service} is outside namespace {ns}")
    for pattern in [*(unit.get("source") or {}).get("include", []), *(unit.get("source") or {}).get("exclude", [])]:
        if pattern.startswith("/") or ".." in pattern.split("/"):
            out.append(f"unit {uid}: source pattern {pattern} must be relative without '..'")
    for check in unit.get("smoke", []):
        kind = check.get("kind")
        if kind == "ha_config_check":
            out.append(f"unit {uid}: ha_config_check belongs to ha_yaml units")
        elif kind == "unit_state":
            if not in_namespace(UNIT_SUFFIX.sub("", check.get("name", "")), ns):
                out.append(f"unit {uid}: smoke unit {check.get('name')} is outside namespace {ns}")
            if "active_state" not in check and "result" not in check:
                out.append(f"unit {uid}: unit_state smoke needs active_state or result")
    return out


def host_unit_invariants(unit: dict, ns: str) -> list[str]:
    uid, out = unit.get("id"), []
    targets = {f.get("target", "") for f in unit.get("files", [])}
    for target in sorted(targets):
        m = HOST_TARGET.match(target)
        if m and m.group(1) in ("lib", "share") and f"unit:{m.group(2).split('/')[0]}.service" not in targets:
            out.append(f"unit {uid}: {target} needs unit:{m.group(2).split('/')[0]}.service in the same unit; a "
                       "directory may only be written together with the service that runs from it, so repo files "
                       "never land where an existing root service executes them")
    for act in unit.get("activate", {}).get("units", []):
        name = act.get("name", "")
        if not in_namespace(UNIT_SUFFIX.sub("", name), ns):
            out.append(f"unit {uid}: activated unit {name} is outside namespace {ns}")
        if act.get("op") == "enable_now" and not name.endswith(".timer"):
            out.append(f"unit {uid}: enable_now is only for .timer units ({name})")
        if act.get("op") == "enable_restart" and not name.endswith(".service"):
            out.append(f"unit {uid}: enable_restart is only for .service units ({name})")
    for check in unit.get("smoke", []):
        kind = check.get("kind")
        if kind == "ha_config_check":
            out.append(f"unit {uid}: ha_config_check belongs to ha_yaml units")
        elif kind == "unit_state":
            if not in_namespace(UNIT_SUFFIX.sub("", check.get("name", "")), ns):
                out.append(f"unit {uid}: smoke unit {check.get('name')} is outside namespace {ns}")
            if "active_state" not in check and "result" not in check:
                out.append(f"unit {uid}: unit_state smoke needs active_state or result")
        elif kind == "file_fresh":
            parts = check.get("path", "").split("/")
            if ".." in parts or not in_namespace(parts[0], ns):
                out.append(f"unit {uid}: file_fresh path {check.get('path')} must sit under /var/lib/<{ns}...>")
    if not unit.get("activate", {}).get("units"):
        out.append(f"unit {uid}: host_files units must activate at least one unit")
    return out


def _unit_values(text: str) -> tuple[dict[str, list[tuple[str, str]]], list[str]]:
    """Parse a systemd unit into {section: [(key, value)]}. Continuations, unknown syntax and duplicates of the
    section headers are reported instead of interpreted."""
    sections: dict[str, list[tuple[str, str]]] = {}
    problems: list[str] = []
    current = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if raw.rstrip().endswith("\\"):
            problems.append(f"line {number}: line continuations are not allowed")
            continue
        if line.startswith("["):
            m = re.fullmatch(r"\[([A-Za-z]+)\]", line)
            if not m:
                problems.append(f"line {number}: malformed section header")
                current = None
                continue
            current = m.group(1)
            if current in sections:
                problems.append(f"line {number}: section [{current}] appears twice")
            sections.setdefault(current, [])
            continue
        m = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)=(.*)", line)
        if not m or current is None:
            problems.append(f"line {number}: expected Key=Value inside a section")
            continue
        sections[current].append((m.group(1), m.group(2).strip()))
    return sections, problems


def _names_protected(token: str, patterns: list[str]) -> bool:
    token = token.strip("\"'")
    if "docker.sock" in token:
        return True
    if not token.startswith("/"):
        return False
    token = posixpath.normpath(token)  # a '..' or '//' must not hide a protected path from the patterns
    probe = [token, token.rstrip("/") + "/x"]
    return any(fnmatch.fnmatchcase(t, pat) for t in probe for pat in patterns)


def unit_lint(text: str, name: str, ns: str, *, service_users: list[str], forbidden_users: list[str] = (),
              protected_paths: list[str] = (), protected_groups: list[str] = (), root_units: list[str] = ()) -> list[str]:
    """Spec section 10.3. Pure: no filesystem or systemd access. The executor adds the live-host checks
    (the user exists and is not a sudo member) before it installs a unit. A .service named in the namespace's
    root_units (host.json, owner-approved) may say User=root, and only that: every other rule still applies."""
    m = UNIT_SUFFIX.search(name)
    if not m:
        return [f"{name}: only .service and .timer units can be installed"]
    kind = m.group(1)
    if not in_namespace(UNIT_SUFFIX.sub("", name), ns):
        return [f"{name}: outside namespace {ns}"]
    sections, out = _unit_values(text)
    for section in sections:
        if section not in UNIT_SECTIONS[kind]:
            out.append(f"[{section}] is not allowed in a .{kind} unit")
    for section, pairs in sections.items():
        allowed = UNIT_ALLOW.get(section, set())
        for key, value in pairs:
            if key not in allowed:
                out.append(f"[{section}] {key} is not on the allow-list")
                continue
            if any(_names_protected(tok, list(protected_paths)) for tok in re.split(r"[\s=,:]+", value)):
                out.append(f"[{section}] {key} names a protected path or docker.sock")
            if key.startswith("Exec"):
                if value[:1] in "+!":
                    out.append(f"[{section}] {key} may not use the '{value[:1]}' prefix")
                head = value.lstrip("-@:")
                if not head.startswith("/"):
                    out.append(f"[{section}] {key} must start with an absolute path")
            if key in UNIT_RELATIONS:
                for target in value.split():
                    base = UNIT_SUFFIX.sub("", target)
                    ok = in_namespace(base, ns) or target in SYSTEM_TARGETS or (key == "After" and target in AFTER_ONLY)
                    if not ok:
                        out.append(f"[{section}] {key}={target} is outside the namespace and not a system target")
            if key in ("StateDirectory", "CacheDirectory", "LogsDirectory"):
                for token in value.split():
                    if not in_namespace(token.split("/")[0], ns):
                        out.append(f"[{section}] {key}={token} is outside namespace {ns}")
            if key == "EnvironmentFile":
                env_path = value.strip().lstrip("-")
                if posixpath.normpath(env_path) != env_path or not env_path.startswith(f"/srv/data/{ns}/"):
                    out.append(f"[{section}] EnvironmentFile={value} must be a file under /srv/data/{ns}/")
            if key in ("ReadWritePaths", "ReadOnlyPaths") and any(t.lstrip("-+!") in ("/", "") for t in value.split()):
                out.append(f"[{section}] {key} may not name /")
    service = dict((k, v) for k, v in sections.get("Service", []))
    if kind == "service":
        if "Service" not in sections:
            out.append("a .service unit needs a [Service] section")
        if service.get("NoNewPrivileges") != "true":
            out.append("[Service] NoNewPrivileges=true is required")
        stype = service.get("Type", "simple")
        if stype not in SERVICE_TYPES:
            out.append(f"[Service] Type={stype} is not one of {sorted(SERVICE_TYPES)}")
        user = service.get("User")
        if not user:
            out.append("[Service] User= is required (a unit without it would run as root)")
        elif user == "root" and name in root_units:
            pass  # host.json root_units: this exact unit is allowed to run as root
        elif user in forbidden_users or user == "root" or user not in service_users:
            out.append(f"[Service] User={user} is not one of this namespace's service users")
        group = service.get("Group")
        if group and not GROUP_NAME.fullmatch(group):
            out.append("[Service] Group= must be a group name (a number or specifier could be gid 0 or a protected group)")
        elif group and (group in protected_groups or group == "root"):
            out.append(f"[Service] Group={group} is a protected group")
    elif "Timer" not in sections:
        out.append("a .timer unit needs a [Timer] section")
    return out


WORKFLOW_PATH = re.compile(r"^\.github/workflows/[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.ya?ml$")
_LAUNCH_CMD = r"run: (?:bash|python3) tools/ci/[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.(?:sh|py)"
LAUNCHER = re.compile(r"^(?P<indent> *)(?P<dash>- )?" + _LAUNCH_CMD + r"$")
RUN_LINE = re.compile(r"^(?P<indent> *)(?P<dash>- )?run:(?: .*)?$")
MAX_WORKFLOW_BYTES = 65536


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_comment(line: str) -> bool:
    return not line.strip() or line.lstrip(" ").startswith("#")


def _run_block(lines: list[str], start: int) -> int:
    """End (exclusive) of the `run:` entry that starts at `start`: itself plus every deeper-indented or blank line."""
    base, end = _indent(lines[start]), start + 1
    while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > base):
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1  # trailing blank lines belong to the next item
    return end


def workflow_lint(old: str, new: str, path: str = ".github/workflows/x.yml") -> list[str]:
    """Pure check for the executor's workflow.propose action (docs/decisions/2026-09-30-workflows-thin-launchers.json).

    An agent may change a workflow file only by (1) editing comments or blank lines and (2) replacing an existing step's
    whole `run:` entry (one line or a block) with ONE launcher line `run: bash|python3 tools/ci/<name>.sh|.py` with no
    arguments, quoting, expansion or chaining, at the same indent. Nothing else may differ: not triggers, permissions,
    secrets, runner labels, `uses:`, `env:`, `if:`, names, step order or any other key. A pure insertion of a run line is
    refused (it would add a step). That the launcher script exists on main is checked by the executor, not here."""
    import difflib

    if not WORKFLOW_PATH.match(path or "") or ".." in path:
        return [f"{path}: only .github/workflows/<name>.yml or .yaml can be proposed"]
    out: list[str] = []
    for label, text in (("current", old), ("proposed", new)):
        if len(text.encode("utf-8", "replace")) > MAX_WORKFLOW_BYTES:
            out.append(f"{label} file is larger than {MAX_WORKFLOW_BYTES} bytes")
        if "\0" in text or "\r" in text or "\t" in text:
            out.append(f"{label} file contains NUL, carriage-return or tab characters")
    if out:
        return out
    a, b = old.split("\n"), new.split("\n")
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        before, after = a[i1:i2], b[j1:j2]
        if all(_is_comment(x) for x in before) and all(_is_comment(x) for x in after):
            continue
        where = f"line {i1 + 1}"
        lead_b = next((n for n, x in enumerate(before) if not _is_comment(x)), len(before))
        lead_a = next((n for n, x in enumerate(after) if not _is_comment(x)), len(after))
        if lead_b == len(before) or lead_a == len(after):
            out.append(f"{where}: only comment or blank lines may be added or removed outside a run replacement")
            continue
        start = i1 + lead_b
        old_run = RUN_LINE.match(a[start])
        if old_run is None:
            out.append(f"{where}: this change is not a replacement of an existing `run:` entry")
            continue
        end = _run_block(a, start)
        if end > i2:
            out.append(f"{where}: the whole `run:` entry must be replaced, not part of it")
            continue
        if not all(_is_comment(x) for x in a[end:i2]):
            out.append(f"{where}: lines after the run entry may only be comments")
            continue
        launcher = LAUNCHER.match(after[lead_a])
        if launcher is None or launcher.group("indent") != old_run.group("indent") or launcher.group("dash") != old_run.group("dash"):
            out.append(f"{where}: the replacement must be exactly `run: bash tools/ci/<script>.sh` (or python3 ... .py) at the same indent")
            continue
        if not all(_is_comment(x) for x in after[lead_a + 1:]):
            out.append(f"{where}: lines after the launcher may only be comments")
    return out


def host_invariants(host: dict) -> list[str]:
    """Trust rules for host.json the schema cannot express. The bootstrap refuses a host.json that fails them."""
    out: list[str] = []
    owner = host.get("owner_user")
    callers = host.get("callers", [])
    caller_users = [c.get("user") for c in callers]
    names = [n.get("namespace") for n in host.get("namespaces", [])]
    repos = [n.get("repository") for n in host.get("namespaces", [])]
    for label, values in (("caller user", caller_users), ("namespace", names), ("repository", repos)):
        dupes = sorted({v for v in values if values.count(v) > 1})
        if dupes:
            out.append(f"duplicate {label}: {', '.join(dupes)}")
    for a in names:
        for b in names:
            if a != b and b.startswith(a):
                out.append(f"namespace {a} is a prefix of {b}; the namespace set must be prefix-free")
    for n in names:
        if in_namespace("platform-executor", n):
            out.append(f"namespace {n} would own the executor's own directories (platform-executor)")
    # legacy_names widen what retired_host_paths may name, so they must not reach into another namespace, another
    # namespace's legacy names or the executor: every name in the combined set stays prefix-free.
    owned = [(n, ns.get("namespace")) for ns in host.get("namespaces", []) for n in [ns.get("namespace"), *ns.get("legacy_names", [])]]
    for a, ns_a in owned:
        if in_namespace("platform-executor", a) or in_namespace(a, "platform-executor"):
            out.append(f"namespace {ns_a}: legacy name {a} would own the executor's own names (platform-executor)")
        for b, ns_b in owned:
            if (a, ns_a) != (b, ns_b) and (a == b or b.startswith(a + "-")) and a != ns_a:
                out.append(f"namespace {ns_a}: legacy name {a} overlaps {b} of namespace {ns_b}")
    for ns in host.get("namespaces", []):
        for user in ns.get("service_users", []):
            if user == "root" or user == owner or user in caller_users:
                out.append(f"namespace {ns.get('namespace')}: service user {user} may not be root, "
                           "the owner user or an executor caller")
    for ns in host.get("namespaces", []):
        app = ns.get("app_release")
        if app:
            user = app.get("service_user")
            if user == "root" or user == owner or user in caller_users:
                out.append(f"namespace {ns.get('namespace')}: app_release.service_user {user} may not be root, the owner user or an executor caller")
            if user not in ns.get("service_users", []):
                out.append(f"namespace {ns.get('namespace')}: app_release.service_user {user} must be one of service_users")
            for service in app.get("services", []):
                if not in_namespace(UNIT_SUFFIX.sub("", service), ns.get("namespace", "")):
                    out.append(f"namespace {ns.get('namespace')}: app_release service {service} is outside the namespace")
            for path in app.get("data_read", []):
                base = f"/srv/data/{ns.get('namespace')}"
                if posixpath.normpath(path) != path or not (path == base or path.startswith(base + "/")):
                    out.append(f"namespace {ns.get('namespace')}: app_release.data_read {path} must be {base} or under it")
            base = f"/srv/data/{ns.get('namespace')}"
            for path in app.get("data_write", []):
                if posixpath.normpath(path) != path or not path.startswith(base + "/"):
                    out.append(f"namespace {ns.get('namespace')}: app_release.data_write {path} must be strictly below {base} (never {base} itself)")
                elif not any(path == r or path.startswith(r + "/") for r in app.get("data_read", [])):
                    out.append(f"namespace {ns.get('namespace')}: app_release.data_write {path} must be inside a data_read path (never wider than its read parent)")
    for ns in host.get("namespaces", []):
        base = f"/srv/data/{ns.get('namespace')}"
        for env in ns.get("container_envelopes", []):
            if env.get("container") not in ns.get("containers", []):
                out.append(f"namespace {ns.get('namespace')}: container_envelopes names {env.get('container')}, which is not in containers")
            for m in env.get("readonly_mounts", []):
                src = m.get("source", "")
                if posixpath.normpath(src) != src or not (src == base or src.startswith(base + "/")):
                    out.append(f"namespace {ns.get('namespace')}: container_envelopes mount source {src} must be {base} or under it")
    for ns in host.get("namespaces", []):
        home = f"/home/{host.get('owner_user')}/"
        base = f"/srv/data/{ns.get('namespace')}/"
        for rec in ns.get("container_recipes", []):
            who = f"namespace {ns.get('namespace')}: container_recipes {rec.get('container')}"
            if rec.get("container") not in ns.get("containers", []):
                out.append(f"{who} is not in containers")
            for m in rec.get("mounts", []):
                src, dst = m.get("source", ""), m.get("destination", "")
                if posixpath.normpath(src) != src or not (src.startswith(home) or src.startswith(base)):
                    out.append(f"{who}: mount source {src} must be under {home} or {base}")
                if posixpath.normpath(dst) != dst or dst == "/" or dst.split("/")[1] in ("proc", "sys", "dev", "run", "etc", "boot", "root"):
                    out.append(f"{who}: mount destination {dst} is not allowed")
            for key in rec.get("env", {}):
                if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", key):
                    out.append(f"{who}: environment name {key} is not an upper-case variable name")
            for port in rec.get("ports", []):
                if int(port.split(":")[0]) < 1024:
                    out.append(f"{who}: published port {port} is a privileged host port")
    for ns in host.get("namespaces", []):
        pv = ns.get("python_venv")
        if pv:
            if not re.fullmatch(r"/srv/apps/[a-z][a-z0-9-]{1,40}", pv.get("root", "")):
                out.append(f"namespace {ns.get('namespace')}: python_venv.root must be /srv/apps/<name> (the bootstrap creates it root-owned)")
            if pv.get("user") in ("root", None) or pv.get("user") not in ns.get("service_users", []):
                out.append(f"namespace {ns.get('namespace')}: python_venv.user must be one of the namespace's service users, never root")
            allowed = [re.sub(r"[-_.]+", "-", a).lower() for a in pv.get("allow", [])]
            if len(set(allowed)) != len(allowed):
                out.append(f"namespace {ns.get('namespace')}: python_venv.allow lists a package twice after normalizing its name")
    for ns in host.get("namespaces", []):
        co = ns.get("checkout")
        if co:
            roots = {r.get("path") for r in ns.get("extra_target_roots", []) if r.get("alias") == "checkout"}
            if co.get("path") not in roots:
                out.append(f"namespace {ns.get('namespace')}: checkout.path must also be an extra_target_roots entry with alias checkout")
            if co.get("user") in ("root", None):
                out.append(f"namespace {ns.get('namespace')}: checkout.user may not be root (git runs as the checkout's owner)")
            for unit in co.get("busy_units", []):
                if not in_namespace(UNIT_SUFFIX.sub("", unit), ns.get("namespace", "")):
                    out.append(f"namespace {ns.get('namespace')}: checkout busy unit {unit} is outside the namespace")
    for ns in host.get("namespaces", []):
        for row in ns.get("handover_paths", []):
            path, user = (row or {}).get("path", ""), (row or {}).get("user")
            if not path.startswith("/var/lib/"):
                out.append(f"namespace {ns.get('namespace')}: handover path {path} must be under /var/lib")
            elif not in_namespace(path[len("/var/lib/"):].split("/")[0], ns.get("namespace", "")):
                out.append(f"namespace {ns.get('namespace')}: handover path {path} is outside namespace {ns.get('namespace')}")
            elif ".." in path.split("/") or path.endswith("/"):
                out.append(f"namespace {ns.get('namespace')}: handover path {path} is not a plain path")
            if user in (None, "root") or (user != owner and user not in ns.get("service_users", [])):
                out.append(f"namespace {ns.get('namespace')}: handover user {user} must be the owner or one of the namespace's service users")
    for ns in host.get("namespaces", []):
        for path in ns.get("retired_host_paths", []):
            why = retired_path_problem(path, ns.get("namespace", ""), tuple(ns.get("legacy_names", [])))
            if why:
                out.append(f"namespace {ns.get('namespace')}: retired path {path} {why}")
        mq = ns.get("mqtt")
        if mq:
            roots = {r.get("alias"): r.get("path") for r in ns.get("extra_target_roots", [])}
            if roots.get("mqtt") != mq.get("config_dir") or roots.get("mqtt_creds") != mq.get("credentials_dir"):
                out.append(f"namespace {ns.get('namespace')}: mqtt.config_dir and mqtt.credentials_dir must also be extra_target_roots "
                           "entries with aliases mqtt and mqtt_creds (the sandbox makes only those writable)")
            if mq.get("container") not in ns.get("containers", []):
                out.append(f"namespace {ns.get('namespace')}: mqtt.container must be one of the namespace's containers")
    for ns in host.get("namespaces", []):
        pg = ns.get("postgres")
        if pg:
            roots = {r.get("alias"): r.get("path") for r in ns.get("extra_target_roots", [])}
            if roots.get("pg_creds") != pg.get("credentials_dir"):
                out.append(f"namespace {ns.get('namespace')}: postgres.credentials_dir must also be an extra_target_roots entry with alias pg_creds "
                           "(the sandbox makes only those writable)")
            if not str(pg.get("role_prefix", "")).startswith(str(ns.get("namespace", "")).split("-")[0]):
                out.append(f"namespace {ns.get('namespace')}: postgres.role_prefix must start with the namespace's own name")
    for ns in host.get("namespaces", []):
        out += root_unit_problems(ns)
    for ns in host.get("namespaces", []):
        if ns.get("owner_review_targets") and not host.get("owner_github_login"):
            out.append(f"namespace {ns.get('namespace')}: owner_review_targets needs owner_github_login in host config")
    if host.get("review_policy") and not host.get("owner_github_login"):
        out.append("review_policy needs owner_github_login in host config (the owner's approval still always wins)")
    requesters = [c for c in callers if "pihole.unblock-request" in c.get("actions", [])]
    if len(requesters) > 1:
        out.append("at most one caller may hold pihole.unblock-request")
    for c in callers:
        user, actions = c.get("user"), c.get("actions", [])
        pihole = [a for a in actions if a.startswith("pihole.")]
        if "pihole.unblock-request" in actions:
            # Owner decision 2026-10-02 (docs/decisions/2026-10-01-pihole-requester-identity.json, option A): agents and the
            # owner share one Unix user, so a "dedicated identity" cannot exist. The shared user may hold the unblock
            # actions; the protection is that hand-made blocks are refused by the action itself, plus audit and the tripwire.
            # A separate (non-owner) requester, if one is ever created, still holds only pihole.* actions.
            if user != owner and len(pihole) != len(actions):
                out.append(f"caller {user}: a dedicated unblock requester may hold only pihole.* actions")
        elif set(pihole) - {"pihole.block-add", "pihole.snapshot", "pihole.names", "pihole.block-restore", "pihole.harden-modes", "pihole.adlist-add"} or \
                (set(pihole) & {"pihole.block-add", "pihole.block-restore", "pihole.harden-modes", "pihole.adlist-add"} and user != owner):
            out.append(f"caller {user}: pihole actions other than snapshot and the owner's block-add belong to the unblock requester")
        if user != owner and set(c.get("container_ops", [])) - {"status"}:
            out.append(f"caller {user}: only the owner may start, stop, restart or read logs")
        if "release" in actions and (len(c.get("namespaces", [])) != 1 or "*" in c.get("namespaces", [])):
            out.append(f"caller {user}: a release caller maps to exactly one namespace")
        for ns in c.get("namespaces", []):
            if ns != "*" and ns not in names:
                out.append(f"caller {user}: unknown namespace {ns}")
    return out


def root_unit_problems(ns: dict) -> list[str]:
    """host.json root_units: the short, owner-approved list of services that may run as root. Each names one .service of
    the namespace, the exact lib:/share:/unit: files it is installed from (its own unit file included), and optionally one
    Wi-Fi interface NetworkManager must leave alone. Its files are owner-review targets (hold window; without
    owner_github_login the release refuses them); nm_unmanaged needs the nm alias so the sandbox can write the drop-in."""
    name, out, seen = ns.get("namespace", ""), [], set()
    for row in ns.get("root_units", []):
        unit = row.get("unit", "")
        if not in_namespace(UNIT_SUFFIX.sub("", unit), name) or not unit.endswith(".service"):
            out.append(f"namespace {name}: root unit {unit} must be a .service inside the namespace")
        targets = row.get("targets", [])
        if f"unit:{unit}" not in targets:
            out.append(f"namespace {name}: root unit {unit} must list its own unit file unit:{unit} in targets")
        for target in targets:
            problem = host_target_problem(target, name)
            if problem:
                out.append(f"namespace {name}: root unit {unit}: {target} {problem}")
            elif target in seen:
                out.append(f"namespace {name}: root unit target {target} is listed twice")
            elif target.startswith("unit:") and target != f"unit:{unit}":
                out.append(f"namespace {name}: root unit {unit} may list only its own unit file, not {target}")
            seen.add(target)
        if row.get("nm_unmanaged"):
            roots = {r.get("alias"): r.get("path") for r in ns.get("extra_target_roots", [])}
            if roots.get("nm") != NM_ROOT:
                out.append(f"namespace {name}: root unit {unit} uses nm_unmanaged, which needs extra_target_roots alias nm = {NM_ROOT}")
    return out


RETIRE_ROOTS = ("/etc/systemd/system/", "/usr/local/sbin/", "/usr/local/lib/", "/usr/local/share/", "/var/lib/", "/etc/sudoers.d/")


def retired_path_problem(path: str, ns: str, legacy: tuple | list = ()) -> str | None:
    """A legacy host path the installer may back up and remove: a top-level entry under one fixed root whose name belongs
    to the namespace (ns or ns-*) or to one of the namespace's legacy_names (the names its broker-era units and helpers
    used, e.g. signal-capture for signal-ops). Removal only ever takes access away; the installer keeps a backup for its rollback."""
    root = next((r for r in RETIRE_ROOTS if path.startswith(r)), None)
    if root is None:
        return f"is not under one of {', '.join(RETIRE_ROOTS)}"
    name = path[len(root):]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@-]{0,120}", name) or name in (".", ".."):
        return "must name one entry directly under its root"
    base = re.sub(r"@?\.(service|socket|timer)$", "", name) if root == "/etc/systemd/system/" else name  # foo@.service is a template
    if not any(in_namespace(base, owner) for owner in (ns, *legacy)):
        return f"is outside namespace {ns}" + (f" and its legacy names {', '.join(legacy)}" if legacy else "")
    if in_namespace(base, "platform-executor"):
        return "belongs to the executor itself"
    return None


def recipe_matches_host(recipe: dict, host: dict) -> list[str]:
    """recipe.namespace must be the namespace host.json maps to recipe.repository, and ha: needs an ha root there."""
    match = [n for n in host.get("namespaces", []) if n.get("repository") == recipe.get("repository")]
    if not match:
        return [f"repository {recipe.get('repository')} is not mapped in host config"]
    ns = match[0]
    out = []
    if recipe.get("namespace") != ns.get("namespace"):
        out.append(f"recipe namespace {recipe.get('namespace')} != host mapping {ns.get('namespace')} "
                   f"for {recipe.get('repository')}")
    units = recipe.get("units", [])
    if any(u.get("kind") == "ha_yaml" for u in units) and not any(
            r.get("alias") == "ha" for r in ns.get("extra_target_roots", [])):
        out.append(f"namespace {ns.get('namespace')} has no ha: target root in host config")
    host_units = [u for u in units if u.get("kind") == "host_files"]
    if host_units and ns.get("host_files") is not True:
        out.append(f"namespace {ns.get('namespace')} is not enabled for host_files in host config")
    if any(f.get("target", "").endswith(".service") for u in host_units for f in u.get("files", [])) \
            and not ns.get("service_users"):
        out.append(f"namespace {ns.get('namespace')} has no service_users, so it cannot install .service units")
    roots = {r.get("unit"): set(r.get("targets", [])) for r in ns.get("root_units", [])}
    owner = {t: unit for unit, targets in roots.items() for t in targets}
    for u in host_units:
        targets = {f.get("target", "") for f in u.get("files", [])}
        for unit, allowed in roots.items():
            if f"unit:{unit}" in targets and targets - allowed:
                out.append(f"unit {u.get('id')}: root unit {unit} may be installed only from its listed files; "
                           f"{', '.join(sorted(targets - allowed))} are not in host config root_units")
        for target in sorted(targets):
            if target in owner and f"unit:{owner[target]}" not in targets:
                out.append(f"unit {u.get('id')}: {target} belongs to root unit {owner[target]} and is written only together with it")
    if any(u.get("kind") == "grafana_dashboard" for u in units) and not ns.get("grafana"):
        out.append(f"namespace {ns.get('namespace')} is not enabled for grafana_dashboard in host config")
    if any(u.get("kind") == "mqtt_accounts" for u in units) and not ns.get("mqtt"):
        out.append(f"namespace {ns.get('namespace')} is not enabled for mqtt_accounts in host config")
    if any(u.get("kind") == "pg_roles" for u in units) and not ns.get("postgres"):
        out.append(f"namespace {ns.get('namespace')} is not enabled for pg_roles in host config")
    if any(u.get("kind") == "git_checkout" for u in units) and not ns.get("checkout"):
        out.append(f"namespace {ns.get('namespace')} is not enabled for git_checkout in host config")
    if any(u.get("kind") == "python_venv" for u in units) and not ns.get("python_venv"):
        out.append(f"namespace {ns.get('namespace')} is not enabled for python_venv in host config")
    if sum(u.get("kind") == "python_venv" for u in units) > 1:
        out.append(f"namespace {ns.get('namespace')}: at most one python_venv unit (one environment per namespace)")
    if sum(u.get("kind") == "git_checkout" for u in units) > 1:
        out.append(f"namespace {ns.get('namespace')}: at most one git_checkout unit (one fixed checkout per namespace)")
    app = ns.get("app_release")
    for u in units:
        if u.get("kind") != "app_release":
            continue
        if not app:
            out.append(f"namespace {ns.get('namespace')} is not enabled for app_release in host config")
            continue
        if app.get("root") != f"/srv/apps/{u.get('app')}":
            out.append(f"unit {u.get('id')}: app {u.get('app')} does not match the namespace's app_release.root {app.get('root')}")
        service = (u.get("activate") or {}).get("service")
        if service not in app.get("services", []):
            out.append(f"unit {u.get('id')}: service {service} is not in the namespace's app_release.services")
    return out


def validate(kind: str, document: Any, host: dict | None = None) -> list[str]:
    found = errors(document, load_schema(kind))
    if found:
        return found
    if kind == "recipe":
        gated = frozenset()
        if host is not None:
            row = next((n for n in host.get("namespaces", []) if n.get("repository") == document.get("repository")), {})
            gated = frozenset(row.get("owner_review_targets", []))
        found += recipe_invariants(document, gated)
        if host is not None:
            found += recipe_matches_host(document, host)
    if kind == "host":
        found += host_invariants(document)
    return found


def _unit_main(argv: list[str]) -> int:
    args = dict(zip(argv[3::2], argv[4::2]))
    if len(argv) < 5 or set(args) - {"--namespace", "--host", "--protected"} or "--namespace" not in args:
        print("usage: validate.py unit FILE --namespace NS [--host HOST_JSON] [--protected PROTECTED_JSON]", file=sys.stderr)
        return 2
    try:
        text = Path(argv[2]).read_text(encoding="utf-8")
        host = json.loads(Path(args["--host"]).read_text(encoding="utf-8")) if "--host" in args else {}
        protected = json.loads(Path(args["--protected"]).read_text(encoding="utf-8")) if "--protected" in args else {}
    except (OSError, ValueError) as exc:
        print(f"cannot read input: {exc}")
        return 1
    ns_name = args["--namespace"]
    ns = next((n for n in host.get("namespaces", []) if n.get("namespace") == ns_name), {})
    callers = [c.get("user") for c in host.get("callers", [])]
    found = unit_lint(text, Path(argv[2]).name, ns_name, service_users=ns.get("service_users", []),
                      forbidden_users=[host.get("owner_user"), *callers], protected_paths=protected.get("host_paths", []),
                      protected_groups=protected.get("users_groups", []),
                      root_units=[r.get("unit") for r in ns.get("root_units", [])])
    for line in found:
        print(line)
    if not found:
        print("OK")
    return 1 if found else 0


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "unit":
        return _unit_main(argv)
    with_host = len(argv) == 5 and argv[1] == "recipe" and argv[3] == "--host"
    if not (len(argv) == 3 or with_host) or argv[1] not in SCHEMAS:
        print(f"usage: validate.py {{{'|'.join(SCHEMAS)}}} FILE  |  validate.py recipe FILE --host HOST_JSON",
              file=sys.stderr)
        return 2
    docs = []
    for path in [argv[2]] + ([argv[4]] if with_host else []):
        try:
            docs.append(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            print(f"cannot read {path}: {exc}")
            return 1
    host = docs[1] if with_host else None
    if host is None:
        found = validate(argv[1], docs[0])
    else:
        found = validate("host", host) or validate("recipe", docs[0], host)
    for line in found:
        print(line)
    if not found:
        print("OK")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
