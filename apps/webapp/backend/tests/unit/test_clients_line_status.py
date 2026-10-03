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
        assert r["manual_agreement_amount"] is None
        assert r["agreed_status"] == "WHITE"
        assert r["paid_status"] == "WHITE"

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


class TestOtherCommentBehaviourUnchanged:
    """T006 - delete / merge / agreement amount / להוריד / unclear-colouring keep working."""

    def test_delete_keyword_still_moves_to_past_and_records_removal(self, tmp_path):
        reader = make_reader(tmp_path, OFFICIAL, _events(), comments={DEBT: "למחוק"})
        report = reader.get_report()
        assert section(report, DEBT) == "past"
        removed = read_json(tmp_path / "clients" / "removed_clients.json", [])
        assert [r["client_name"] for r in removed] == [DEBT]

    def test_merge_keyword_still_merges(self, tmp_path):
        comments = {NO_AGREEMENT: f'לאחד עם "{DEBT}"'}
        report = make_reader(tmp_path, OFFICIAL, _events(), comments=comments).get_report()
        names = [r["official_name"] for r in report["clients"]]
        assert NO_AGREEMENT not in names
        assert row(report, DEBT)["display_paid"] == 2500
        assert NO_AGREEMENT in row(report, DEBT)["raw_names"]

    def test_agreement_amount_keyword_still_sets_manual_amount(self, tmp_path):
        report = make_reader(tmp_path, OFFICIAL, _events(), comments={NO_AGREEMENT: "הסכם 5,000"}).get_report()
        r = row(report, NO_AGREEMENT)
        assert r["manual_agreement_amount"] == 5000
        assert r["display_agreed"] == 5000
        assert r["agreed_status"] == "GRAY"

    def test_remove_duplicate_deposit_keyword_still_marks_paid_gray(self, tmp_path):
        events = _events() + [
            ev("B1", DEBT, "בנק", 700, subtype="הפקדה"),
            ev("B2", DEBT, "בנק", 700, subtype="הפקדה"),
        ]
        report = make_reader(tmp_path, OFFICIAL, events, comments={DEBT: "להוריד כפילות"}).get_report()
        assert row(report, DEBT)["paid_status"] == "GRAY"

    def test_unclear_keywords_still_colour_amounts_yellow(self, tmp_path):
        comments = {DEBT: "לבדוק", PAID: "לא ברור", NO_AGREEMENT: "חסר מסמך"}
        report = make_reader(tmp_path, OFFICIAL, _events(), comments=comments).get_report()
        for c in comments:
            assert row(report, c)["agreed_status"] == "YELLOW", c
        assert section(report, DEBT) == "debt"
