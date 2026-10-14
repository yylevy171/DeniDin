"""Comments -> Agreements DB migration script, against a real denidin-app Agreements API process
(same fixture as the facade tests). Prompts are driven through the script's injectable input function."""
import json

import pytest

from tests.integration.test_agreements_endpoints import TOKEN, denidin_api  # noqa: F401

pytestmark = pytest.mark.integration

NAME = "איציק בן שלוש"
COMMENT = ('הסכם 28.1.26 9000, ״ליווי מול הבודקת״; הסכם 29.4 - 7000, ״שימוע משמעת״; סה״כ הסכמים 16000.')


def _answers(*items):
    it = iter(items)
    return lambda _prompt: next(it)


def _setup(tmp_path, comments):
    clients = tmp_path / "clients"
    clients.mkdir()
    (clients / "client_comments.json").write_text(json.dumps(comments, ensure_ascii=False), encoding="utf-8")
    return clients, tmp_path / "state.json"


def _client(url):
    from webapp_backend.agreements_client import AgreementsClient
    return AgreementsClient(url, TOKEN)


def _agreements(client, name=NAME):
    return client.request("GET", "/agreements", params={"client_name": name})[1]["agreements"]


class TestParser:
    def test_reads_clauses_amounts_dates_and_the_stated_total(self):
        from scripts.migrate_comments_to_agreements import parse_comment
        parsed = parse_comment(COMMENT)
        assert [c["amount"] for c in parsed["clauses"]] == [9000, 7000]
        assert parsed["clauses"][0]["date_text"] == "28.1.26"
        assert parsed["clauses"][1]["date_text"] == "29.4.26"  # year taken from the previous clause
        assert parsed["stated_total"] == 16000

    def test_plus_amounts_are_summed_and_chat_noise_is_dropped(self):
        from scripts.migrate_comments_to_agreements import parse_comment
        parsed = parse_comment("הסכם 15.10.24 - 2000+500, 10/15/24, 19:17 - אילה: אבי לוי 2,500₪")
        assert parsed["clauses"][0]["amount"] == 2500 and parsed["clauses"][0]["parts"] == [2000, 500]
        assert not parsed["clauses"][0]["text"].startswith("10/15")

    def test_no_clause_when_no_amount(self):
        from scripts.migrate_comments_to_agreements import parse_comment
        assert parse_comment("אין הסכם. לבדוק!")["clauses"] == []


class TestRun:
    def test_accept_edit_and_resume(self, tmp_path, denidin_api):  # noqa: F811
        from scripts.migrate_comments_to_agreements import run
        clients, state = _setup(tmp_path, {NAME: COMMENT, "אחר": "אין הסכם"})
        api = _client(denidin_api)
        out = []
        counts = run(clients, api, state, input_fn=_answers("a", "q"), out=out.append)
        assert counts["created"] == 1 and counts["quit"] == 1
        made = _agreements(api)
        assert len(made) == 1 and made[0]["components"][0]["amount"] == 9000
        assert made[0]["status"] == "Active" and "נוצר מהערת הלקוח" in made[0]["agreement_description"]
        # resume: the first clause is not asked again; edit the second one
        counts = run(clients, api, state, input_fn=_answers("e", "", "", "7500", ""), out=out.append)
        assert counts["created"] == 1 and counts["quit"] == 0
        assert sorted(c["amount"] for a in _agreements(api) for c in a["components"]) == [7500, 9000]

    def test_duplicate_amount_defaults_to_skip_and_creates_nothing(self, tmp_path, denidin_api):  # noqa: F811
        from scripts.migrate_comments_to_agreements import run
        clients, state = _setup(tmp_path, {NAME: COMMENT})
        api = _client(denidin_api)
        assert api.request("POST", "/agreements", body={
            "client_name": NAME, "title": "קיים", "components": [{"label": "א", "amount": 9000}]})[0] == 200
        out = []
        counts = run(clients, api, state, input_fn=_answers("", "a"), out=out.append)  # Enter = default
        assert counts["duplicates"] == 1 and counts["skipped"] == 1 and counts["created"] == 1
        assert any("DUPLICATE" in line for line in out)
        assert sorted(c["amount"] for a in _agreements(api) for c in a["components"]) == [7000, 9000]

    def test_dry_run_asks_nothing_and_writes_nothing(self, tmp_path, denidin_api):  # noqa: F811
        from scripts.migrate_comments_to_agreements import run
        clients, state = _setup(tmp_path, {NAME: COMMENT})
        api = _client(denidin_api)
        counts = run(clients, api, state, dry_run=True, input_fn=_answers(), out=lambda _l: None)
        assert counts["created"] == 0 and _agreements(api) == []
