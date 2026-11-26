"""Self-check of the platform kit in this repo. Run: python3 -m unittest platform.kit.test_kit  (or python3 platform/kit/test_kit.py)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reason  # noqa: E402
import work_items  # noqa: E402


class KitTests(unittest.TestCase):
    def test_every_file_matches_the_manifest(self):
        manifest = json.loads((HERE / "kit.json").read_text())
        for name, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((HERE / name).read_bytes()).hexdigest(), digest, f"{name} was edited here; edit the platform's kit/ instead")

    def test_reason_codes_are_complete_and_refuse_unknown_ones(self):
        codes = json.loads((HERE / "reason_codes.json").read_text())["codes"]
        for row in codes:
            self.assertEqual(set(row), {"code", "result", "retry", "owner_needed", "next_action"})
        self.assertIsNotNone(reason.lookup("TESTS_FAILED"))
        self.assertIsNone(reason.lookup("MADE_UP"))

    def test_reason_cli_prints_json_writes_the_summary_and_fails_unless_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = os.path.join(tmp, "s.md")
            env = dict(os.environ, GITHUB_STEP_SUMMARY=summary)
            done = subprocess.run([sys.executable, str(HERE / "reason.py"), "TESTS_FAILED", "two tests failed"], capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(json.loads(done.stdout.splitlines()[0])["code"], "TESTS_FAILED")
            self.assertIn("::error title=TESTS_FAILED::", done.stdout)
            self.assertIn("TESTS_FAILED", Path(summary).read_text())
            warn = subprocess.run([sys.executable, str(HERE / "reason.py"), "CHECKS_PENDING", "waiting", "--warn"], capture_output=True, text=True, env=env)
            self.assertEqual(warn.returncode, 0)
            self.assertEqual(subprocess.run([sys.executable, str(HERE / "reason.py"), "NOPE", "x"], capture_output=True, text=True).returncode, 2)

    def test_the_repos_work_items_file_is_valid(self):
        data = json.loads((HERE.parent / "work-items.json").read_text())
        self.assertEqual(work_items.problems(data), [])

    def test_validator_names_real_problems(self):
        bad = {"schema": "platform-work-items-v1", "items": [
            {"id": "a-one", "title": "x", "status": "todo", "owner": "agent", "priority": 5, "acceptance": "it works for sure", "depends_on": ["ghost"]},
            {"id": "a-one", "title": "y", "status": "oops", "owner": "bot", "priority": 500, "acceptance": "short"}]}
        found = " | ".join(work_items.problems(bad))
        for needle in ("duplicate id", "status must be", "owner must be", "priority must be", "acceptance must", "unknown item ghost"):
            self.assertIn(needle, found)

    def test_ask_rows_are_checked_when_present(self):
        base = {"title": "t", "owner": "tito", "acceptance": "check it works", "status": "todo", "priority": 5}
        good = {"schema": "platform-work-items-v1", "items": [dict(base, id="ask-ok", ask={
            "question": "Approve PR 416?", "recommended": "approve", "due": "2026-10-07", "default": None, "link": "https://github.com/x/y/pull/416"})]}
        self.assertEqual(work_items.problems(good), [])
        bad = {"schema": "platform-work-items-v1", "items": [dict(base, id="ask-bad", ask={"question": "", "due": "tomorrow", "link": "ftp://x", "default": 3})]}
        found = " | ".join(work_items.problems(bad))
        for needle in ("ask.question", "ask.recommended", "ask.due", "ask.default", "ask.link"):
            self.assertIn(needle, found)
        self.assertIn("ask must be an object", " | ".join(work_items.problems({"schema": "platform-work-items-v1", "items": [dict(base, id="ask-str", ask="no")]})))

    def test_brief_fields_are_checked_when_present(self):
        base = {"title": "t", "owner": "agent", "acceptance": "check it works", "status": "todo", "priority": 5}
        good = {"schema": "platform-work-items-v1", "items": [dict(base, id="brief-ok", allowed_paths=["docs/**"], files_to_read=["README.md"],
                                                                  tests_to_run=["python3 -m unittest"], rung_hint="python")]}
        self.assertEqual(work_items.problems(good), [])
        bad = {"schema": "platform-work-items-v1", "items": [dict(base, id="brief-bad", allowed_paths=["/etc/x"], files_to_read="README.md", tests_to_run=[], rung_hint="magic")]}
        found = " | ".join(work_items.problems(bad))
        for needle in ("allowed_paths entries are repo-relative", "files_to_read must be a list", "tests_to_run must be a list", "rung_hint must be"):
            self.assertIn(needle, found)

    def test_the_pull_request_check_wants_a_valid_item_line(self):
        import check_pr
        ids = {"real-item"}
        self.assertEqual(check_pr.problems("Does a thing.\n\nitem: real-item", "claude/x", ids), [])
        self.assertEqual(check_pr.problems("x\nitem: platform:kit-carries-rules\n", "claude/x", ids), [])
        self.assertEqual(check_pr.problems("", "platform/kit-abc123", ids), [])
        self.assertIn("no `item: <id>` line", check_pr.problems("Just a description", "claude/x", ids)[0])
        self.assertIn("is not on this repo's work list", check_pr.problems("x\nitem: made-up-id", "claude/x", ids)[0])
        self.assertIn("no `item: <id>` line", check_pr.problems("the item: real-item is inline, not a line of its own... item:real", "b", ids)[0])
        with tempfile.TemporaryDirectory() as tmp:
            event = os.path.join(tmp, "event.json")
            Path(event).write_text(json.dumps({"pull_request": {"body": "no line here", "head": {"ref": "claude/x"}}}))
            done = subprocess.run([sys.executable, str(HERE / "check_pr.py")], capture_output=True, text=True, env=dict(os.environ, GITHUB_EVENT_PATH=event))
            self.assertEqual(done.returncode, 1)
            self.assertIn("::error title=TABLE_RULES::", done.stdout)
            Path(event).write_text(json.dumps({"ref": "refs/heads/main"}))
            done = subprocess.run([sys.executable, str(HERE / "check_pr.py")], capture_output=True, text=True, env=dict(os.environ, GITHUB_EVENT_PATH=event))
            self.assertEqual(done.returncode, 0)

    def test_boundaries_are_a_list_and_the_check_names_the_rule_never_the_line(self):
        import boundary
        ids = [r["id"] for r in boundary.rules()]
        for needed in ("external-action", "data-destroy", "credentials", "permissions", "network-dns", "protection-off", "live-control"):
            self.assertIn(needed, ids)
        diff = "\n".join([
            "--- a/app/send.py", "+++ b/app/send.py", "@@ -1 +1,2 @@", "+server = smtplib.SMTP('mail')", " unchanged",
            "--- /dev/null", "+++ b/deploy/key.pem", "@@ -0,0 +1 @@", "+x",
            "--- a/docs/readme.md", "+++ b/docs/readme.md", "@@ -1 +1 @@", "+plain words about email and tokens",
            "--- a/db/migrate.sql", "+++ b/db/migrate.sql", "@@ -1 +1 @@", "+DROP TABLE users;"])
        found = boundary.hits(boundary.parse_diff(diff))
        self.assertEqual(sorted((h["rule"], h["path"]) for h in found),
                         [("credentials", "deploy/key.pem"), ("data-destroy", "db/migrate.sql"), ("external-action", "app/send.py")])
        self.assertNotIn("SMTP", json.dumps(found))
        self.assertEqual(boundary.hits(boundary.parse_diff("--- a/docs/x.md\n+++ b/docs/x.md\n@@ -1 +1 @@\n+hello\n")), [])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "d.diff")
            Path(path).write_text(diff)
            done = subprocess.run([sys.executable, str(HERE / "boundary.py"), "check", "--diff", path], capture_output=True, text=True)
            self.assertEqual(done.returncode, 3)
            self.assertIn("::warning title=BOUNDARY", done.stdout)
        self.assertEqual(subprocess.run([sys.executable, str(HERE / "boundary.py"), "capability", "email.send"], capture_output=True).returncode, 3)
        self.assertEqual(subprocess.run([sys.executable, str(HERE / "boundary.py"), "capability", "file.read"], capture_output=True).returncode, 0)

    def test_the_role_an_item_needs_comes_from_data_never_from_the_model(self):
        import roles as role_cards
        table = role_cards.work_types()
        known = {r["id"] for r in role_cards.shared()}
        self.assertTrue(set(table["kinds"].values()) <= known)
        self.assertFalse(set(table["kinds"]) & set(table["person_work"]))
        r = role_cards.resolve
        self.assertEqual(r({"kind": "fix"})["role"], "builder")
        self.assertEqual(r({"kind": "investigation"})["role"], "investigator")
        self.assertEqual(r({"kind": "fix", "role": "investigator"})["how"], "item")  # the item's own role wins
        self.assertEqual((r({"kind": "decision"})["role"], r({"kind": "decision"})["how"]), (None, "person"))
        self.assertEqual((r({"kind": "measure"})["role"], r({"kind": "measure"})["how"]), ("planner", "needs_label"))
        self.assertEqual(r({})["role"], "planner")  # no kind: the planner labels it, nothing is guessed
        self.assertEqual(r({"role": "wizard"})["how"], "needs_label")  # an unknown role is not accepted

    def test_role_cards_are_data_and_a_product_may_add_but_not_redefine(self):
        import roles as role_cards
        shared = [r["id"] for r in role_cards.shared()]
        self.assertEqual(shared, ["builder", "investigator", "researcher", "reviewer", "repairer", "planner"])
        for row in role_cards.shared():
            self.assertIn(row.get("uses_model"), ("now", "later", "sometimes"), row["id"])
            self.assertTrue(row.get("justified_by"), f"{row['id']}: every role says why it exists")
            self.assertIsInstance(row.get("item_role"), bool, f"{row['id']}: item_role says whether an item may name it")
        self.assertEqual([r["id"] for r in role_cards.shared() if r["item_role"]], ["builder", "investigator"])
        for row in role_cards.shared():
            for field in role_cards.FIELDS:
                self.assertTrue(row.get(field), f"{row.get('id')}: {field}")
        self.assertEqual(role_cards.role_for({"id": "x"})["id"], "builder")
        self.assertEqual(role_cards.role_for({"id": "x", "role": "investigator"})["may_change"][:4], "only")
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "roles.json"
            good.write_text(json.dumps({"roles": [{"id": "plaid-sync", "does": "pulls transactions", "reads": "plaid", "may_change": "the ledger tables", "hands_back": "row counts", "stops_when": "synced"}]}))
            self.assertEqual(role_cards.local_problems(good), [])
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"roles": [{"id": "builder", "does": "x"}, {"id": "Bad Id"}]}))
            found = " | ".join(role_cards.local_problems(bad))
            self.assertIn("already defined", found)
            self.assertIn("id must be", found)
        base = {"title": "t", "owner": "agent", "acceptance": "check it works", "status": "todo", "priority": 5}
        data = {"schema": "platform-work-items-v1", "items": [dict(base, id="role-ok", role="researcher"), dict(base, id="role-bad", role="wizard")]}
        found = work_items.problems(data)
        self.assertEqual(len(found), 1)
        self.assertIn("role 'wizard'", found[0])

    def test_next_skips_waiting_blocked_and_done_items(self):
        base = {"title": "t", "owner": "agent", "acceptance": "check it works"}
        data = {"schema": "platform-work-items-v1", "items": [
            dict(base, id="done-one", status="done", priority=1),
            dict(base, id="ready-low", status="todo", priority=10, depends_on=["done-one"]),
            dict(base, id="ready-high", status="todo", priority=50),
            dict(base, id="blocked", status="todo", priority=99, depends_on=["ready-low"]),
            dict(base, id="waiting", status="todo", priority=98, waiting_on="owner", next_step="needs the owner")]}
        self.assertEqual([i["id"] for i in work_items.next_items(data, 5)], ["ready-high", "ready-low"])


class OwnerRepliesTests(unittest.TestCase):
    """The owner's replies on the Needs you page reach the worker that owns the item (owner 2026-10-17: replies must not need relaying)."""

    DATA = {"items": [{"id": "mine-1"}, {"id": "mine-2"}]}
    DOC = {"answers": {"owner-replies/mine-1": {"choice": "yes", "note": "go", "at": 5}, "owner-replies/other-repo-item": {"choice": "no", "at": 6},
                       "room-standard-2026-10-17/R1": {"choice": "other", "note": "x", "at": 7}}}

    def test_only_this_repos_items_and_only_row_replies_come_back(self):
        self.assertEqual({"mine-1": {"reply": "yes", "words": "go", "at": 5}}, work_items.owner_replies(self.DATA, fetch=lambda: self.DOC))

    def test_an_unreachable_hub_never_blocks_the_worker(self):
        def down():
            raise OSError("no hub")
        self.assertEqual({}, work_items.owner_replies(self.DATA, fetch=down))
        self.assertEqual({}, work_items.owner_replies(self.DATA, fetch=lambda: (_ for _ in ()).throw(ValueError("bad json"))))


if __name__ == "__main__":
    unittest.main()
