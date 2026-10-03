"""Feature 092 T007 - the one-time migration turns today's comment keywords into persisted line
statuses, so no line changes section on deploy.

The parity oracle (``_legacy_section``) is a FROZEN copy of the pre-092 routing, taken from
``clients_reader._apply_status_directives`` + ``_row_status`` at commit f096e06. It lives here
deliberately (not imported from src): it is the yardstick the new code is measured against.
"""
import re

from tests.clients_helpers import (
    MIGRATION_KEY,
    agreement,
    make_reader,
    payment,
    read_json,
    row,
    section,
)


def _legacy_section(comment: str, agreed: float, paid: float, is_past: bool) -> str:
    """Pre-092 section for a non-merged client with no ``הסכם``/``להוריד`` keywords."""
    is_active = "לקוח פעיל" in comment or "לקוחה פעילה" in comment
    is_delete = "למחוק" in comment or comment.strip() == "להסיר" or "להסיר מהרשימה" in comment
    is_check = is_close = False
    if not is_delete:
        is_check = "לבדוק" in comment
        is_close = ("לסגור" in comment or "אפשר לסגור" in comment) and not is_check
    if is_delete:
        is_past = True
    if is_check:
        return "check"
    if is_active:
        return "active"
    if is_close:
        return "settled"
    if is_past:
        return "past"
    if agreed > 0 and round(paid, 2) == round(agreed, 2):
        return "settled"
    if agreed > 0 and paid < agreed:
        return "debt"
    return "missing_agreement"


def _legacy_status(comment: str):
    """The single status the migration must store: the highest of check > active > closed."""
    sec = _legacy_section(comment, 10000, 2000, False)
    return {"check": "check", "active": "active", "settled": "closed"}.get(sec)


MATRIX = [
    "לבדוק",
    "לקוח פעיל",
    "לקוחה פעילה",
    "לסגור",
    "אפשר לסגור",
    "לבדוק ואז לסגור",
    "לקוח פעיל - למחוק",
    "לקוח פעיל, לסגור",
    "לקוח פעיל, לבדוק",
    "למחוק",
    "להסיר",
    "שילם בשיק, לסגור בסוף החודש",
    "סתם הערה בלי מילות מפתח",
]


def _matrix_reader(tmp_path, profile):
    """One client per matrix comment. profile = (agreed, paid)."""
    agreed, paid = profile
    clients = [f"לקוח {i:02d}" for i in range(len(MATRIX))]
    events = []
    for i, c in enumerate(clients):
        if agreed:
            events.append(agreement(f"A{i}", c, agreed))
        if paid:
            events.append(payment(f"C{i}", c, paid))
    comments = dict(zip(clients, MATRIX))
    return clients, comments, make_reader(tmp_path, clients, events, comments=comments, migrated=False)


class TestSectionParity:
    def test_every_matrix_comment_keeps_its_section_debt_profile(self, tmp_path):
        clients, comments, reader = _matrix_reader(tmp_path, (10000, 2000))
        report = reader.get_report()
        for c in clients:
            assert section(report, c) == _legacy_section(comments[c], 10000, 2000, False), comments[c]

    def test_every_matrix_comment_keeps_its_section_paid_profile(self, tmp_path):
        clients, comments, reader = _matrix_reader(tmp_path, (3000, 3000))
        report = reader.get_report()
        for c in clients:
            assert section(report, c) == _legacy_section(comments[c], 3000, 3000, False), comments[c]

    def test_stored_status_is_the_highest_legacy_flag(self, tmp_path):
        clients, comments, reader = _matrix_reader(tmp_path, (10000, 2000))
        reader.get_report()
        stored = read_json(tmp_path / "clients" / "client_status.json", {})
        for c in clients:
            assert stored.get(c) == _legacy_status(comments[c]), comments[c]

    def test_migrated_closed_line_shows_real_amounts(self, tmp_path):
        clients, comments, reader = _matrix_reader(tmp_path, (10000, 2000))
        report = reader.get_report()
        closed = next(c for c in clients if comments[c] == "לסגור")
        r = row(report, closed)
        assert (r["display_agreed"], r["display_paid"]) == (10000, 2000)


class TestMigrationMechanics:
    def test_marker_written_with_israel_local_offset(self, tmp_path):
        _, _, reader = _matrix_reader(tmp_path, (10000, 2000))
        reader.get_report()
        marker = read_json(tmp_path / "clients" / "migrations.json", {})
        assert MIGRATION_KEY in marker
        assert re.search(r"[+-]\d\d:\d\d$", marker[MIGRATION_KEY])

    def test_runs_once_even_across_a_restart(self, tmp_path):
        clients, comments, reader = _matrix_reader(tmp_path, (10000, 2000))
        reader.get_report()
        status_path = tmp_path / "clients" / "client_status.json"
        checked = next(c for c in clients if comments[c] == "לבדוק")
        stored = read_json(status_path)
        del stored[checked]
        status_path.write_text(__import__("json").dumps(stored, ensure_ascii=False), encoding="utf-8")

        # a brand-new reader over the same files = a backend restart
        events = [agreement(f"A{i}", c, 10000) for i, c in enumerate(clients)]
        restarted = make_reader(tmp_path, clients, events, migrated=False)
        report = restarted.get_report()
        assert checked not in read_json(status_path)
        assert section(report, checked) != "check"

    def test_never_overwrites_an_existing_status(self, tmp_path):
        events = [agreement("A1", "דנה", 10000), payment("C1", "דנה", 2000)]
        reader = make_reader(
            tmp_path, ["דנה"], events,
            comments={"דנה": "לבדוק"}, status={"דנה": "active"}, migrated=False,
        )
        report = reader.get_report()
        assert read_json(tmp_path / "clients" / "client_status.json") == {"דנה": "active"}
        assert section(report, "דנה") == "active"

    def test_comments_file_is_byte_identical(self, tmp_path):
        _, _, reader = _matrix_reader(tmp_path, (10000, 2000))
        path = tmp_path / "clients" / "client_comments.json"
        before = path.read_bytes()
        reader.get_report()
        assert path.read_bytes() == before

    def test_merged_away_client_gets_no_status(self, tmp_path):
        events = [agreement("A1", "דנה", 10000), agreement("A2", "דן", 1000)]
        reader = make_reader(
            tmp_path, ["דנה", "דן"], events,
            comments={"דן": 'לאחד עם "דנה" ולסגור'}, migrated=False,
        )
        reader.get_report()
        assert "דן" not in read_json(tmp_path / "clients" / "client_status.json", {})
