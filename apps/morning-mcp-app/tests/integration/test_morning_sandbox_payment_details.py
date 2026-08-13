"""bugfix-028 (A2, A3, A3b) — real Morning-sandbox tests for what a created
document actually STORES: its VAT treatment, its payment date, its payment
method, and the bank details behind it.

Every assertion here is an independent follow-up `get_invoice` read of the
persisted document, never the create response — the create response was
proven (probe, 2026-08-09) to carry no `total`/`amount` at all, which is
bugfix-028's A4 in the first place.

Behaviour these tests are written against is live-verified sandbox
behaviour, not documentation (CONSTITUTION: NO UNVERIFIED THIRD-PARTY
ASSUMPTIONS). From the 2026-08-09 probe rounds:
  - omitting `vatType` on a type-300 is treated exactly as vatType=0
    ("price EXCLUDES vat"), so 11 is stored as 12.98; vatType=1 stores 11.
  - a `payment` array is persisted only on types 320/400 - a 300/305
    returns `payment: []` even when the line was accepted.
  - bank details persist ONLY on payment type 4 (העברה בנקאית), under
    `bankName`/`bankBranch`/`bankAccount`; type 1 (מזומן) drops them all.
  - bit is type 10 + appType 1, and does persist `transactionId`.

RED ON CURRENT CODE (that is the point - see METHODOLOGY §VII step 4):
the tools take no VAT argument on a type 300, no payment date, no payment
method and no bank details, so these fail with TypeError until the fix
lands. The two amount assertions fail on the stored value instead.

No mocking (CONSTITUTION §I/§V) - real sandbox documents throughout.
"""
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import (
    create_combo_document,
    create_transaction_account,
)
from denidin_mcp_morning.utils.time_utils import now_local
from tests.integration._seed_helpers import seed_real_client

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

# The screenshot date used throughout bugfix-028's evidence (Bank-test-image.jpg
# is value-dated 12/07/2026) - deliberately not "today", since a same-day
# assertion cannot distinguish a correct date from the hardcoded one.
TXN_DATE = "2026-07-12"


@pytest.fixture(scope="module")
def morning_client():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )


def _unique_marker(label):
    """Unique per CALL, not per second: seed_real_client derives the client's
    email from this, and Morning rejects a duplicate email (400). Parametrized
    cases run well inside the same second, so a timestamp alone collides."""
    return f"DENIDIN_028_{label}_{int(now_local().timestamp())}_{uuid.uuid4().hex[:6]}"


def _find_document(morning_client, client_name, expected_type):
    """Locate the freshly created document by client + type, then read it back
    in full. Polls because the sandbox's search index lags writes briefly
    (same eventual-consistency class as _seed_helpers)."""
    for _ in range(12):
        found = morning_client.list_invoices({"clientName": client_name})
        items = found if isinstance(found, list) else (found.get("items") or [])
        for item in items:
            if item.get("type") == expected_type:
                return morning_client.get_invoice(str(item.get("id")))
        time.sleep(1.5)
    raise AssertionError(
        f"No type-{expected_type} document ever appeared for client {client_name!r}"
    )


# --------------------------------------------------------------------- A2
def test_transaction_account_vat_included_stores_the_amount_asked_for(morning_client):
    """A2: a type-300 for 47 ₪ *including* VAT must be stored by Morning as 47,
    not 55.46.

    Today `create_transaction_account` has no VAT argument at all and its
    payload omits `vatType` entirely, which Morning treats as "price excludes
    VAT" and inflates by ~18% (live-confirmed: 11 -> 12.98, and in production
    2,360 -> 2,784.80 on document 90195).
    """
    marker = _unique_marker("A2_INCL")
    _, client_name = seed_real_client(morning_client, marker)

    create_transaction_account(
        morning_client,
        client_name=client_name,
        amount=47.0,
        description=f"VAT-included transaction account {marker}",
        vat_included=True,
        name_resolved=True,
    )

    stored = _find_document(morning_client, client_name, expected_type=300)
    assert stored["amount"] == 47.0, (
        f"Morning stored {stored['amount']!r} for a document approved at 47.0 - "
        f"the user approves one number and the system creates another (A2/A4). "
        f"income={stored.get('income')!r}"
    )


def test_transaction_account_vat_excluded_stores_the_grossed_up_amount(morning_client):
    """A2, the other side: when the amount is explicitly *before* VAT, the
    stored total is legitimately larger - what must never happen is that
    being decided silently. 47 before VAT is 55.46."""
    marker = _unique_marker("A2_EXCL")
    _, client_name = seed_real_client(morning_client, marker)

    create_transaction_account(
        morning_client,
        client_name=client_name,
        amount=47.0,
        description=f"VAT-excluded transaction account {marker}",
        vat_included=False,
        name_resolved=True,
    )

    stored = _find_document(morning_client, client_name, expected_type=300)
    assert stored["amount"] == pytest.approx(55.46, abs=0.01), (
        f"expected 47 + 18% = 55.46, Morning stored {stored['amount']!r}"
    )


def test_transaction_account_requires_an_explicit_vat_decision(morning_client):
    """A2 requirement 1 (user, 2026-08-09): VAT is mandatory at creation -
    "unknown" is not a permitted state. Omitting it must be a hard error, not
    a silent default."""
    marker = _unique_marker("A2_MISSING")
    _, client_name = seed_real_client(morning_client, marker)

    with pytest.raises(TypeError):
        create_transaction_account(  # pylint: disable=missing-kwoa
            morning_client,
            client_name=client_name,
            amount=47.0,
            description=f"No VAT decision {marker}",
            name_resolved=True,
        )


# --------------------------------------------------------------------- A3
def test_combo_document_carries_the_real_transaction_date(morning_client):
    """A3: the payment line must carry the date the money actually moved
    (12/07/2026 on the evidence screenshot), not the date the document
    happened to be issued.

    A same-day assertion could not tell a correct date from the hardcoded
    `today`, which is exactly why no existing test caught this.
    """
    marker = _unique_marker("A3_DATE")
    _, client_name = seed_real_client(morning_client, marker)

    create_combo_document(
        morning_client,
        client_name=client_name,
        amount=47.0,
        description=f"Deposit-backed combo {marker}",
        vat_included=True,
        payment_date=TXN_DATE,
        name_resolved=True,
    )

    stored = _find_document(morning_client, client_name, expected_type=320)
    payments = stored.get("payment") or []
    assert payments, "type-320 documents do persist a payment array - none came back"
    assert payments[0]["date"] == TXN_DATE, (
        f"payment date is {payments[0]['date']!r}, expected the real transaction "
        f"date {TXN_DATE!r} (document date staying 'today' is correct and in scope-out)"
    )
    assert stored["documentDate"] != TXN_DATE, (
        "the DOCUMENT date must still be today - only the payment line carries "
        "the transaction date (scope settled with the user)"
    )


@pytest.mark.parametrize(
    "bad_date, why",
    [
        (None, "A3-T3: no transaction date could be established"),
        ("not-a-date", "A3-T4: the date was extracted but is unparseable"),
        ("2026-13-45", "A3-T4: date-shaped but not a real date"),
        # A third case, ("07/12/2026", "ambiguous/non-ISO form"), was REMOVED
        # 2026-08-09: DD/MM/YYYY is now accepted deliberately - it is this
        # project's own persisted ledger form and what Israeli bank
        # confirmations print, so rejecting it meant our own captured date
        # could not be passed to our own tool. Calling it "ambiguous" was my
        # over-reach, not the user's requirement (which was a date that is
        # missing, badly extracted, or in the future); nothing in this system
        # emits MM/DD, so there is nothing to disambiguate.
    ],
)
def test_combo_document_refuses_a_missing_or_unusable_payment_date(morning_client, bad_date, why):
    """A3-T3/T4: a payment-backed document whose transaction date is missing or
    unusable must FAIL rather than quietly substituting today - substituting is
    precisely how four production documents got the wrong date."""
    marker = _unique_marker("A3_BAD")
    _, client_name = seed_real_client(morning_client, marker)

    with pytest.raises(ValueError):
        create_combo_document(
            morning_client,
            client_name=client_name,
            amount=47.0,
            description=f"{why} {marker}",
            vat_included=True,
            payment_date=bad_date,
            name_resolved=True,
        )


def test_combo_document_refuses_a_future_payment_date(morning_client):
    """A3-T5: money cannot have arrived tomorrow. A future transaction date is
    a extraction failure, not a valid input."""
    marker = _unique_marker("A3_FUTURE")
    _, client_name = seed_real_client(morning_client, marker)
    tomorrow = (now_local().date() + timedelta(days=1)).isoformat()

    with pytest.raises(ValueError):
        create_combo_document(
            morning_client,
            client_name=client_name,
            amount=47.0,
            description=f"Future-dated deposit {marker}",
            vat_included=True,
            payment_date=tomorrow,
            name_resolved=True,
        )


# -------------------------------------------------------------------- A3b
def test_bank_deposit_is_booked_as_a_bank_transfer_with_its_bank_details(morning_client):
    """A3b: a document backed by a bank deposit books as payment type 4
    (העברה בנקאית) carrying the bank details from the screenshot - NOT as type
    1 (מזומן), which Morning silently strips every bank field from.

    The "all payments are booked as cash" decision was reversed by the user on
    2026-08-09. Field names are the live-confirmed ones: bankName/bankBranch/
    bankAccount (not branchNumber/accountNumber, which Morning drops).
    """
    marker = _unique_marker("A3B_BANK")
    _, client_name = seed_real_client(morning_client, marker)

    create_combo_document(
        morning_client,
        client_name=client_name,
        amount=47.0,
        description=f"Bank-transfer deposit {marker}",
        vat_included=True,
        payment_date=TXN_DATE,
        # bugfix-028 (user, 2026-08-10): the extraction prompt captures the
        # bank's NUMBER, not its name - "31" here, matching Bank-test-image.jpg's
        # real "מספר בנק מחויב" value, not an invented bank name.
        bank_number="31",
        bank_branch="613",
        bank_account="123456",
        name_resolved=True,
    )

    stored = _find_document(morning_client, client_name, expected_type=320)
    payment = (stored.get("payment") or [{}])[0]

    assert payment.get("type") == 4, (
        f"a bank deposit must book as type 4 (העברה בנקאית), got "
        f"{payment.get('type')!r} ({payment.get('name')!r})"
    )
    # Morning's own JSON field is still called "bankName" (its real API contract,
    # live-confirmed) - it is free text and happily stores our bank NUMBER.
    assert payment.get("bankName") == "31"
    assert payment.get("bankBranch") == "613"
    assert payment.get("bankAccount") == "123456"


def test_bit_deposit_is_booked_as_a_payment_app_carrying_its_reference(morning_client):
    """A3b, laying the land for bit (user, 2026-08-09): bit is type 10 +
    appType 1, and unlike a bank transfer it DOES persist the reference number
    (אסמכתה) as `transactionId`."""
    marker = _unique_marker("A3B_BIT")
    _, client_name = seed_real_client(morning_client, marker)

    create_combo_document(
        morning_client,
        client_name=client_name,
        amount=47.0,
        description=f"bit deposit {marker}",
        vat_included=True,
        payment_date=TXN_DATE,
        payment_method="bit",
        transaction_reference="987654321",
        name_resolved=True,
    )

    stored = _find_document(morning_client, client_name, expected_type=320)
    payment = (stored.get("payment") or [{}])[0]

    assert payment.get("type") == 10, f"bit must book as a payment app, got {payment.get('type')!r}"
    assert payment.get("appType") == 1, f"bit is appType 1, got {payment.get('appType')!r}"
    assert payment.get("transactionId") == "987654321"
