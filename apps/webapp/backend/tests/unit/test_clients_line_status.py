"""Feature 092 (absorbs bugfix-068) - a client line's section comes from the persisted
``client_status.json``, not from comment keywords; closing never touches the amounts.

T004 routing from the status file, T005 the bugfix-068 regression, T006 comments no longer
route while every other comment-driven behaviour stays exactly as before."""
import logging

from tests.clients_helpers import (
    OLD,
    agreement,
    ev,
    make_reader,
    payment,
    read_json,
    row,
    section,
)

DEBT = "לקוח חוב"  # agreed 10,000 / paid 2,000
PAID = "לקוח משלם"  # agreed 3,000 / paid 3,000
NO_AGREEMENT = "לקוח בלי הסכם"  # agreed 0 / paid 500
PAST = "לקוח עבר"  # activity only before the 2025-09-01 cutoff


def _events():
    return [
        agreement("A1", DEBT, 10000), payment("C1", DEBT, 2000),
        agreement("A2", PAID, 3000), payment("C2", PAID, 3000),
        payment("C3", NO_AGREEMENT, 500),
        agreement("A4", PAST, 4000, when=OLD),
    ]


OFFICIAL = [DEBT, PAID, NO_AGREEMENT, PAST]


class TestRoutingFromStatusFile:
    """T004"""

    def test_no_status_routes_by_numbers(self, tmp_path):
        report = make_reader(tmp_path, OFFICIAL, _events()).get_report()
        assert section(report, DEBT) == "debt"
        assert section(report, PAID) == "settled"
        assert section(report, NO_AGREEMENT) == "missing_agreement"
        assert section(report, PAST) == "past"

    def test_each_status_routes_to_its_section(self, tmp_path):
        status = {DEBT: "closed", PAID: "check", NO_AGREEMENT: "active"}
        report = make_reader(tmp_path, OFFICIAL, _events(), status=status).get_report()
        assert section(report, DEBT) == "settled"
        assert section(report, PAID) == "check"
        assert section(report, NO_AGREEMENT) == "active"

    def test_report_exposes_line_status(self, tmp_path):
        report = make_reader(tmp_path, OFFICIAL, _events(), status={DEBT: "check"}).get_report()
        assert row(report, DEBT)["line_status"] == "check"
        assert row(report, PAID)["line_status"] is None

    def test_any_status_outranks_past(self, tmp_path):
        for value, expected in (("closed", "settled"), ("check", "check"), ("active", "active")):
            sub = tmp_path / value
            report = make_reader(sub, OFFICIAL, _events(), status={PAST: value}).get_report()
            assert section(report, PAST) == expected, value

    def test_closed_line_is_flagged_manually_settled(self, tmp_path):
        report = make_reader(tmp_path, OFFICIAL, _events(), status={DEBT: "closed"}).get_report()
        assert row(report, DEBT)["is_manually_settled"] is True
        assert row(report, PAID)["is_manually_settled"] is False

    def test_unknown_stored_value_is_ignored_with_warning(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger="webapp_backend")
        report = make_reader(tmp_path, OFFICIAL, _events(), status={DEBT: "bogus"}).get_report()
        assert section(report, DEBT) == "debt"
        assert row(report, DEBT)["line_status"] is None
        assert any("bogus" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


class TestBugfix068CloseKeepsRealAmounts:
    """T005"""

    def test_closed_debt_line_shows_real_agreed_and_paid(self, tmp_path):
        report = make_reader(tmp_path, OFFICIAL, _events(), status={DEBT: "closed"}).get_report()
        r = row(report, DEBT)
        assert r["status"] == "settled"
        assert r["display_agreed"] == 10000
        assert r["display_paid"] == 2000
        assert r["invoices_net"] == 2000

    def test_closed_line_without_payment_keeps_zero_paid(self, tmp_path):
        report = make_reader(tmp_path, OFFICIAL, _events(), status={NO_AGREEMENT: "closed"}).get_report()
        r = row(report, NO_AGREEMENT)
        assert r["status"] == "settled"
        assert r["display_agreed"] == 0
        assert r["display_paid"] == 500


class TestCommentsNoLongerRoute:
    """T006 - after migration, the three button keywords in a comment are plain text."""

    def test_close_check_active_keywords_do_not_route(self, tmp_path):
        clients = [f"לקוח {i}" for i in range(5)]
        keywords = ["לסגור", "אפשר לסגור", "לבדוק", "לקוח פעיל", "לקוחה פעילה"]
        events = []
        for i, c in enumerate(clients):
            events += [agreement(f"A{i}", c, 10000), payment(f"C{i}", c, 2000)]
        comments = dict(zip(clients, keywords))
        report = make_reader(tmp_path, clients, events, comments=comments).get_report()
        for c, kw in comments.items():
            r = row(report, c)
            assert r["status"] == "debt", kw
            assert r["display_agreed"] == 10000, kw
            assert r["display_paid"] == 2000, kw
            assert r["comment"] == kw


class TestCommentsAreNotParsed:
    """2026-10-14: a comment is a free-text note. No keyword in it changes anything."""

    def test_no_keyword_in_a_comment_changes_a_row(self, tmp_path):
        keywords = {
            DEBT: "למחוק", NO_AGREEMENT: f'לאחד עם "{DEBT}". הסכם 5,000. סה״כ הסכמים 9000',
            PAID: "לבדוק, לא ברור, חסר. להוריד כפילות",
        }
        events = _events() + [ev("B1", DEBT, "הפקדה", 700, subtype="בנק"), ev("B2", DEBT, "הפקדה", 700, subtype="בנק")]
        plain = make_reader(tmp_path / "a", OFFICIAL, events).get_report()
        noted = make_reader(tmp_path / "b", OFFICIAL, events, comments=keywords).get_report()
        assert [r["official_name"] for r in plain["clients"]] == [r["official_name"] for r in noted["clients"]]
        for c in OFFICIAL:
            a, b = row(plain, c), row(noted, c)
            for key in ("status", "display_agreed", "display_paid", "raw_names", "events"):
                assert a[key] == b[key], (c, key)
            assert b["comment"] == keywords.get(c, "")
        assert not (tmp_path / "b" / "clients" / "removed_clients.json").exists()
