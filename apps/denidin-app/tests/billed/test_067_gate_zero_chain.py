"""Feature 067 "no turn" redesign - Gate Zero probes of OpenAI's response chaining (CONSTITUTION: no
unverified third-party assumptions). Real, tiny, text-only calls. Each test records one fact the design
relies on; the observed values are printed so they can be copied into research.md.

C1 a chain continues across separate calls even when `instructions` change between them
C2 prompt-cache behaviour: same instructions vs changed instructions on a continued chain
C3 `truncation="auto"` is accepted on a continued call
C4 what a rejected / unknown previous_response_id looks like (the fallback must catch exactly this)
"""
import logging
from pathlib import Path

import pytest
from openai import APIStatusError, OpenAI

from src.models.config import AppConfiguration

pytestmark = pytest.mark.billed
logger = logging.getLogger(__name__)

BIG = "Reference text. " + ("The quick brown fox jumps over the lazy dog. " * 400)  # > 1024 tokens, cacheable


@pytest.fixture(scope="module")
def ai():
    path = Path(__file__).resolve().parents[2] / "config" / "config.test.json"
    if not path.exists():
        pytest.skip("config.test.json not found")
    config = AppConfiguration.from_file(str(path))
    return OpenAI(api_key=config.ai_api_key), config.ai_model


def _cached(response) -> int:
    details = getattr(response.usage, "input_tokens_details", None)
    return int(getattr(details, "cached_tokens", 0) or 0)


def test_c1_chain_continues_when_instructions_change(ai):
    client, model = ai
    first = client.responses.create(model=model, instructions="You are terse.", max_output_tokens=200,
                                    input="Remember the code word PINEAPPLE. Reply OK.")
    second = client.responses.create(model=model, previous_response_id=first.id, max_output_tokens=200,
                                     instructions="You are a different assistant now. Be terse.",
                                     input="What was the code word? Reply with the word only.")
    logger.warning("GATE-ZERO C1 second reply: %s", second.output_text)
    assert "PINEAPPLE" in (second.output_text or "").upper()


def test_c2_cache_with_same_vs_changed_instructions(ai):
    """The chain itself is made large (a big user message), so cacheability does not depend on the
    instructions' size: any drop in cached tokens is caused by the changed instructions alone."""
    client, model = ai
    first = client.responses.create(model=model, instructions="You are terse. Variant A.", max_output_tokens=200,
                                    input=BIG + "\nSay OK.")
    same = client.responses.create(model=model, previous_response_id=first.id,
                                   instructions="You are terse. Variant A.", max_output_tokens=200,
                                   input="Say OK again.")
    changed = client.responses.create(model=model, previous_response_id=same.id,
                                      instructions="You are terse. Variant B, changed after loading a flow.",
                                      max_output_tokens=200, input="Say OK once more.")
    logger.warning("GATE-ZERO C2 cached tokens: first=%s same-instructions=%s changed-instructions=%s "
                   "(input_tokens first=%s same=%s changed=%s)", _cached(first), _cached(same), _cached(changed),
                   first.usage.input_tokens, same.usage.input_tokens, changed.usage.input_tokens)
    assert changed.usage.input_tokens > 1024  # the chain is big enough to be cacheable


def test_c3_truncation_auto_is_accepted(ai):
    client, model = ai
    first = client.responses.create(model=model, max_output_tokens=200, input="Say OK.")
    second = client.responses.create(model=model, previous_response_id=first.id, truncation="auto",
                                     max_output_tokens=200, input="Say OK again.")
    logger.warning("GATE-ZERO C3 truncation=auto accepted, status: %s", second.status)
    assert second.status == "completed"


def test_c4_unknown_previous_response_id_error_shape(ai):
    client, model = ai
    with pytest.raises(APIStatusError) as caught:
        client.responses.create(model=model, previous_response_id="resp_does_not_exist_000",
                                max_output_tokens=200, input="Say OK.")
    error = caught.value
    logger.warning("GATE-ZERO C4 status=%s type=%s body=%s", error.status_code, type(error).__name__,
                   getattr(error, "body", None))
    assert error.status_code in (400, 404)
