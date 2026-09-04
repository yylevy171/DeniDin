"""bugfix-028 — the image-classification building block, on its own.

This exists because that block was NOT consistent: on 2026-08-09 the same real
bank screenshot was classified as a ledger-worthy deposit
on one run and not on the next, within an hour, with no code change between
them. The document could hardly be clearer - payer, amount, date, branch,
account and reference all read correctly - so "the model was unsure" is not an
acceptable answer for a case this easy.

What changed (user's design, 2026-08-09): the VISION call now classifies, and
returns structured JSON, because it is the only step that actually sees the
image. The old design threw the image away and asked a second, text-only model
to re-derive the document type from prose - prose that happened to include the
extractor's own "ביטחון: בינוני" hedge about a blurry name, which is what tipped
it to "not an event".

There are exactly three outcomes: `bank`, `agreement`, `unknown`. The first two
are entirely different documents, so a misread should land on `unknown` - which
asks the user - never on the wrong one of the pair. PDFs and DOCX files are
never `bank`.

One test per fixture image, deliberately: a single parametrized test that stops
at the first failure would hide which images are unstable, and instability is
the whole subject here.

@pytest.mark.expensive: every test makes a real vision call.
"""
import logging
from pathlib import Path

import pytest

from src.handlers.extractors.image_extractor import (
    DOC_TYPE_AGREEMENT,
    DOC_TYPE_BANK,
    DOC_TYPE_UNKNOWN,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.expensive

FIXTURES = Path(__file__).parent.parent / "fixtures" / "media" / "ledger_events"


@pytest.fixture(scope="module")
def config():
    """Real credentials, isolated test_data/ root - same shape as this
    directory's other expensive suites."""
    from src.models.config import AppConfiguration
    from tests.e2e_helpers import sanity_worker_data_root

    config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
    if not config_path.exists():
        pytest.skip("config.test.json not found")

    cfg = AppConfiguration.from_file(str(config_path))
    cfg.validate()
    test_data_root = sanity_worker_data_root()  # per-xdist-worker under the parallel sanity sweep (Feature 075)
    cfg.data_root = str(test_data_root)
    cfg.memory['session']['storage_dir'] = str(test_data_root / "sessions")
    cfg.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
    return cfg


@pytest.fixture(scope="module")
def image_extractor(config):
    """The extractor alone. Deliberately NOT the whole message pipeline: this
    suite tests one building block, so a failure here can only mean the block
    itself."""
    import denidin
    from src.handlers.extractors.image_extractor import ImageExtractor

    if denidin.denidin_app is None:
        denidin.denidin_app = denidin.initialize_app({
            'green_api_instance_id': config.green_api_instance_id,
            'green_api_token': config.green_api_token,
            'ai_api_key': config.ai_api_key,
            'ai_model': config.ai_model,
            'ai_vision_model': config.ai_vision_model,
            'ai_embedding_model': config.ai_embedding_model,
            'ai_reply_max_tokens': config.ai_reply_max_tokens,
            'log_level': config.log_level,
            'data_root': config.data_root,
            'feature_flags': config.feature_flags,
            'godfather_phone': config.godfather_phone,
            'memory': config.memory,
            'constitution_config': config.constitution_config,
            'user_roles': config.user_roles,
            'mcp': config.mcp,
        })
    return ImageExtractor(denidin.denidin_app)


def _classify(image_extractor, filename):
    """Run one real image through extraction only - no ledger call, no document
    creation, nothing downstream. This is the building block in isolation."""
    from src.models.media import Media

    path = FIXTURES / filename
    assert path.exists(), f"fixture missing: {path}"

    media = Media(data=path.read_bytes(), mime_type="image/jpeg", filename=filename)
    result = image_extractor.analyze_media(media)

    logger.info(
        f"{filename}: doc_type={result.get('doc_type')!r} "
        f"fields={result.get('fields')!r} "
        f"missing={result.get('missing_required_fields')!r}"
    )
    return result


def _assert_text_was_extracted(result):
    """The extractor's job: text off the document. It authors nothing the user
    reads - MediaHandler composes that from this text plus any question - so
    what is asserted here is that real content came back, and that raw JSON
    never leaks through as if it were content."""
    extracted = result.get("raw_response") or ""
    assert extracted.strip(), "no text was extracted from the document at all"
    assert not extracted.strip().startswith("{"), (
        f"unparsed JSON leaked through as extracted text: {extracted[:120]!r}"
    )


@pytest.mark.sanity
def test_bank_test_image_is_classified_as_a_bank_deposit(image_extractor):
    """A real bank-transfer confirmation screenshot.

    Ground truth read directly off the image (Deposit_Eti.jpeg, 2026-09-04), not
    from any model's description of it - a sharp, printed banking-app screenshot:

        תאריך פעולה / יום ערך  05/08/2026
        מספר אסמכתה            3317
        שם חשבון מחויב         אסולין אסתר
        מספר בנק מחויב         31
        מספר סניף מחויב        112
        מספר חשבון מחויב       105397180
        הערות                  שליחות וצילום הערעור לעיריה
        סכום                   ₪554.00

    Both name tokens ("אסתר", "אסולין") are asserted, order-independent - the
    name is printed twice (the free-text header "העברה מאסולין אסתר חשבון..."
    and the labelled row "שם חשבון מחויב  אסולין אסתר"), both legible and
    cross-checking each other, so a dropped letter is still a real failure.

    NOTE: if this test starts failing after 20+ invoices accumulate in the
    Morning sandbox for this payer (the model may refuse to create an apparent
    duplicate), swap in a fresh bank screenshot with a new payer name, one-time
    seed that client in Morning, and add the name to
    tests/fixtures/morning_sandbox_clients.json.
    """
    result = _classify(image_extractor, "Deposit_Eti.jpeg")

    assert result["doc_type"] == DOC_TYPE_BANK, (
        f"a bank transfer confirmation must classify as {DOC_TYPE_BANK!r}, got "
        f"{result['doc_type']!r} - extracted text was: {result.get('raw_response')!r}"
    )
    fields = result["fields"]
    assert float(fields.get("amount")) == 554, f"amount: {fields.get('amount')!r}"
    assert fields.get("txn_date") == "05/08/2026", f"txn_date: {fields.get('txn_date')!r}"
    payer_tokens = set(str(fields.get("payer_name") or "").split())
    assert {"אסתר", "אסולין"} <= payer_tokens, (
        f"payer_name: {fields.get('payer_name')!r} - the name is printed twice in "
        f"this image and both copies are legible"
    )
    assert str(fields.get("bank_number")) == "31", f"bank_number: {fields.get('bank_number')!r}"
    assert str(fields.get("bank_branch")) == "112", f"bank_branch: {fields.get('bank_branch')!r}"
    assert str(fields.get("bank_account")) == "105397180", f"bank_account: {fields.get('bank_account')!r}"
    assert not result["missing_required_fields"], (
        f"every required field is present in this document, yet these were "
        f"reported missing: {result['missing_required_fields']}"
    )
    _assert_text_was_extracted(result)


def test_kehilat_tzair_deposit_is_classified_as_a_bank_deposit(image_extractor):
    """A second, visually different real bank confirmation (₪9,440, קהילת צעיר,
    "זיכוי ממס\"ב") - one screenshot layout passing proves nothing about the
    next, and the user's own note is that bank screenshots vary."""
    result = _classify(image_extractor, "bank_deposit_kehilat_tzair.jpg")

    assert result["doc_type"] == DOC_TYPE_BANK, (
        f"got {result['doc_type']!r} - summary was: {result.get('raw_response')!r}"
    )
    assert float(result["fields"].get("amount")) == 9440, f"amount: {result['fields'].get('amount')!r}"
    _assert_text_was_extracted(result)


def test_idan_shabtai_agreement_is_classified_as_an_agreement(image_extractor):
    """A real signed fee-agreement letter (עידן שבתאי, tiered 20,000/60,000/
    8,000 ₪ + VAT)."""
    result = _classify(image_extractor, "agreement_idan_shabtai.jpg")

    assert result["doc_type"] == DOC_TYPE_AGREEMENT, (
        f"got {result['doc_type']!r} - summary was: {result.get('raw_response')!r}"
    )
    assert result["fields"].get("components"), "an agreement must carry its fee components"
    _assert_text_was_extracted(result)


def test_multi_component_agreement_is_classified_as_an_agreement(image_extractor):
    """A real fee proposal with FOUR distinct components (שחר פישר / עו"ד אילה
    הוניגמן) - the component split is Feature 033's territory, but the
    classification must hold regardless of how many components there are."""
    result = _classify(image_extractor, "Agreement-test-image.jpg")

    assert result["doc_type"] == DOC_TYPE_AGREEMENT, (
        f"got {result['doc_type']!r} - summary was: {result.get('raw_response')!r}"
    )
    _assert_text_was_extracted(result)


@pytest.mark.sanity
def test_six_component_agreement_is_classified_as_an_agreement(image_extractor):
    """A real photographed fee proposal (מור בן שעיה), harder to read than the
    others - a photo rather than a clean scan."""
    result = _classify(image_extractor, "Agreement-mor.jpg")

    assert result["doc_type"] == DOC_TYPE_AGREEMENT, (
        f"got {result['doc_type']!r} - summary was: {result.get('raw_response')!r}"
    )
    _assert_text_was_extracted(result)


@pytest.mark.sanity
def test_personal_note_is_neither_bank_nor_agreement(image_extractor):
    """A handwritten personal note, confirmed during the AHLedger project's own
    audit NOT to be a fee agreement.

    The important half of classification: this must NOT be forced *cleanly*
    into one of the two real buckets, and nothing may be captured off it.
    `unknown` is the ideal answer (it makes the system ask instead of
    inventing a ledger event); a real bucket that is at least flagged
    incomplete - so the system still asks rather than committing - is also
    acceptable. Asking is success here, not failure.
    """
    result = _classify(image_extractor, "not_an_agreement_personal_note.jpg")

    # Never acceptable: a confident, complete real-bucket classification.
    forced_cleanly = (
        result["doc_type"] != DOC_TYPE_UNKNOWN
        and not result.get("missing_required_fields")
    )
    assert not forced_cleanly, (
        f"model confidently classified a personal handwritten note as "
        f"{result['doc_type']!r} with no missing fields - expected 'unknown', "
        f"or at least an incomplete flag so the system asks. "
        f"summary was: {result.get('raw_response')!r}"
    )
    # Never acceptable: an actual ledger event captured off this note.
    assert not result.get("ledger_events"), (
        f"a ledger event was captured off an ambiguous personal note: "
        f"{result.get('ledger_events')!r}"
    )
    _assert_text_was_extracted(result)


# --- Real WhatsApp images from tests/fixtures/media/ (user request, 2026-08-10:
# "run it on the 3 whatsapp images ... that will be the final confirmation").
# Unlike the ledger_events/ fixtures these are ordinary phone screenshots, with
# status bars, app chrome and, in one case, a whole email client around the
# content - closer to what really arrives over WhatsApp.
WHATSAPP_FIXTURES = Path(__file__).parent.parent / "fixtures" / "media"


def _classify_whatsapp(image_extractor, filename):
    from src.models.media import Media

    path = WHATSAPP_FIXTURES / filename
    assert path.exists(), f"fixture missing: {path}"
    media = Media(data=path.read_bytes(), mime_type="image/jpeg", filename=filename)
    result = image_extractor.analyze_media(media)
    logger.info(
        f"{filename}: doc_type={result.get('doc_type')!r} "
        f"fields={result.get('fields')!r} missing={result.get('missing_required_fields')!r}"
    )
    return result


def test_whatsapp_marciano_bibi_fee_proposal_is_an_agreement(image_extractor):
    """Ground truth read off the image: an אילה הוניגמן letterhead הצעת שכר טרחה
    dated 12.1.26 for אלונה מרציאנו ביבי - 9,500 ₪ כולל מע"מ, 6,000 ₪ כולל מע"מ,
    plus 7% of any award. Photographed with the phone's status bar in frame."""
    result = _classify_whatsapp(image_extractor, "WhatsApp Image 2026-01-13 at 18.01.21.jpeg")

    assert result["doc_type"] == DOC_TYPE_AGREEMENT, (
        f"got {result['doc_type']!r} - extracted text was: {result.get('raw_response')!r}"
    )
    assert "מרציאנו" in (result["fields"].get("client_name") or ""), (
        f"client_name: {result['fields'].get('client_name')!r}"
    )
    assert result["fields"].get("components"), "an agreement must carry its fee components"
    _assert_text_was_extracted(result)


def test_whatsapp_mendel_shmulik_fee_proposal_is_an_agreement(image_extractor):
    """Ground truth read off the image: הצעת שכר טרחה dated 24.11.2025 for
    חנות דגים מנדל שמוליק - 9,000 ₪ לפני מע"מ, hourly 600 ₪ capped at 10 hours,
    and 7,000 ₪ לפני מע"מ. Mixes fixed and hourly components, and states VAT the
    opposite way round from the other proposal."""
    result = _classify_whatsapp(image_extractor, "WhatsApp Image 2025-11-24 at 13.30.28.jpeg")

    assert result["doc_type"] == DOC_TYPE_AGREEMENT, (
        f"got {result['doc_type']!r} - extracted text was: {result.get('raw_response')!r}"
    )
    assert result["fields"].get("components"), "an agreement must carry its fee components"
    _assert_text_was_extracted(result)


def test_whatsapp_email_screenshot_is_never_a_bank_deposit(image_extractor):
    """A Gmail screenshot: רמי לוסטיג replying "שלחי לי את חשבון הבנק ואעביר לך",
    with Ayala Honigman's fee terms (5,000 ₪ כתב הגנה, +5,000 ₪ if proceedings)
    quoted underneath.

    The hard requirement is that this is NOT a bank deposit: no money has moved,
    someone is ASKING for bank details in order to pay later. Classifying it as
    `bank` would invent a deposit that never happened - the most damaging
    possible misread, since it would feed a receipt for money not received.

    Whether it should be `agreement` (fee terms are genuinely stated and the
    client accepts them) or `unknown` (it is an email screenshot, not a
    document) is a business judgement, deliberately left open here rather than
    asserted on my own authority.
    """
    result = _classify_whatsapp(image_extractor, "WhatsApp Image 2025-11-18 at 21.51.25.jpeg")

    assert result["doc_type"] != DOC_TYPE_BANK, (
        f"no money moved in this screenshot - someone is asking for bank details "
        f"in order to transfer later. Classifying it as a deposit would invent a "
        f"payment that never happened. Extracted: {result.get('raw_response')!r}"
    )
    _assert_text_was_extracted(result)
