"""Feature 067 Gate Zero V1 probe. AUTHORED, NOT RUN. Needs its own go-ahead (real, tiny OpenAI call).

Question: does the Responses API accept a user input item next to a function_call_output when
continuing with previous_response_id? The hand-back merge (Backbone._compose_follow_up_input) relies on
it. If this fails, switch the single composition seam to the plan's fallback D4 (a separate follow-up call).
"""
from pathlib import Path

import pytest
from openai import OpenAI

from src.models.config import AppConfiguration

pytestmark = pytest.mark.billed


def test_function_output_and_user_message_in_one_follow_up_input():
    path = Path(__file__).resolve().parents[2] / "config" / "config.test.json"
    if not path.exists():
        pytest.skip("config.test.json not found")
    config = AppConfiguration.from_file(str(path))
    client = OpenAI(api_key=config.ai_api_key)
    tool = {"type": "function", "name": "lookup", "description": "Look something up.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            "strict": True}
    first = client.responses.create(model=config.ai_model, input="Call lookup once.", tools=[tool],
                                    max_output_tokens=200)
    call = next(i for i in first.output if i.type == "function_call")
    second = client.responses.create(
        model=config.ai_model, previous_response_id=first.id, tools=[tool], max_output_tokens=200,
        input=[{"type": "function_call_output", "call_id": call.call_id, "output": "done"},
               {"role": "user", "content": "Also: reply with the single word PINEAPPLE."}])
    assert "PINEAPPLE" in (second.output_text or "").upper()
