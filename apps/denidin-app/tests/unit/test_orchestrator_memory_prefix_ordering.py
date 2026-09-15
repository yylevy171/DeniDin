"""Unit tests (Feature 063, 2026-09-15 gap fix - found on re-audit against
contracts/prompt-assembly.md's own formula): BackboneOrchestrator.build_instructions
must place `_turn_memory_context` AFTER the capability content, never between
`backbone` and the capability's own prompt - REQ-063-06 requires
`backbone_content + load_capability_prompt(tag)` to form one of only 9 distinct
byte-stable prefixes system-wide (contracts/prompt-assembly.md), and recalled
memory varies per turn/query, so placing it earlier would silently break every
call from ever sharing a cached prefix with another call using the same tag."""
from src.backbone.capability_tags import CapabilityTag
from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration


def _orchestrator(prompts_root):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(object(), config)


def _prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE-TEXT", encoding="utf-8")
    (base / "prompts" / "capabilities" / "ledger_query.md").write_text(
        "LEDGER-QUERY-CAPABILITY-TEXT", encoding="utf-8",
    )
    return base


def test_memory_context_appears_after_capability_content_not_before(tmp_path):
    orchestrator = _orchestrator(_prompts_root(tmp_path))
    orchestrator._turn_memory_context = "RECALLED MEMORIES (from past conversations):\n- x"

    instructions = orchestrator.build_instructions(CapabilityTag.LEDGER_QUERY)

    backbone_idx = instructions.index("BACKBONE-TEXT")
    capability_idx = instructions.index("LEDGER-QUERY-CAPABILITY-TEXT")
    memory_idx = instructions.index("RECALLED MEMORIES")
    assert backbone_idx < capability_idx < memory_idx


def test_backbone_plus_capability_prefix_is_identical_across_different_memory_contexts(tmp_path):
    """The whole point of REQ-063-06: two calls with the SAME active_tag but
    DIFFERENT recalled memory must still share an identical
    `backbone + capability_prompt` prefix - proving the memory placement doesn't
    break prompt-cache eligibility for the capability tier."""
    root = _prompts_root(tmp_path)
    orch_a = _orchestrator(root)
    orch_a._turn_memory_context = "RECALLED MEMORIES: turn A's own recall results"
    instructions_a = orch_a.build_instructions(CapabilityTag.LEDGER_QUERY)

    orch_b = _orchestrator(root)
    orch_b._turn_memory_context = "RECALLED MEMORIES: a completely different turn B recall"
    instructions_b = orch_b.build_instructions(CapabilityTag.LEDGER_QUERY)

    # The longest common prefix of the two instructions must extend at least
    # through both the backbone AND the capability content - i.e. the point
    # where they diverge must be at/after "LEDGER-QUERY-CAPABILITY-TEXT", not
    # somewhere inside or before it.
    common_len = 0
    for char_a, char_b in zip(instructions_a, instructions_b):
        if char_a != char_b:
            break
        common_len += 1
    common_prefix = instructions_a[:common_len]
    assert "BACKBONE-TEXT" in common_prefix
    assert "LEDGER-QUERY-CAPABILITY-TEXT" in common_prefix
    assert instructions_a != instructions_b  # they DO differ overall (memory tail differs)


def test_no_memory_context_omits_the_block_entirely(tmp_path):
    orchestrator = _orchestrator(_prompts_root(tmp_path))
    orchestrator._turn_memory_context = ""

    instructions = orchestrator.build_instructions(CapabilityTag.LEDGER_QUERY)
    assert "RECALLED MEMORIES" not in instructions
