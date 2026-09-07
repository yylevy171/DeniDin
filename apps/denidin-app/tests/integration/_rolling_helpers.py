"""Shared fixtures for the Feature 070 rolling-window / daily-roll integration
tests — a real `AIHandler` on an isolated tmp data_root with OpenAI mocked at the
network boundary only (responses + embeddings), same convention as
`test_rolling_window_integration.py`.
"""
from types import SimpleNamespace

from src.models.config import AppConfiguration

_EMBED_VOCAB = [
    "פגישה", "רואה", "חשבון", "בנק", "הפקדה", "חוזה", "הסכם", "לקוח",
    "מחר", "היום", "דחוף", "תשלום", "חשבונית", "קבלה", "ILS", "אלפא",
]


def fake_client(capture, *, embed_dim=8):
    """`.responses.create` captures kwargs and echoes the input transcript in
    `output_text` (so a token in a message reaches a summary → the embedding
    call); `.embeddings.create` returns a deterministic vector."""
    def responses_create(**kwargs):
        capture.append(kwargs)
        echoed = kwargs.get("input")
        if isinstance(echoed, list):
            echoed = " ".join(str(i.get("content", "")) for i in echoed)
        return SimpleNamespace(
            id=f"resp_{len(capture)}", output=[], output_text="SUMMARY: " + str(echoed or ""),
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=5, input_tokens=3, output_tokens=2),
        )

    def embeddings_create(model, input):  # noqa: A002 - OpenAI's own kwarg name
        # A crude but *content-sensitive* fake: a bag-of-words vector over a fixed
        # vocabulary, so texts that share words get a high cosine similarity and
        # unrelated texts do not. Enough to make recall ranking meaningful without
        # a real embedding model (constitution: no internal mocks of our own code,
        # only this external boundary).
        text = str(input)
        vocab = _EMBED_VOCAB[:embed_dim] if embed_dim <= len(_EMBED_VOCAB) else _EMBED_VOCAB
        vec = [float(text.count(w)) for w in vocab]
        # pad / fill so an all-zero vector (no vocab hit) still normalises
        if not any(vec):
            vec = [0.01] * len(vocab)
        return SimpleNamespace(data=[SimpleNamespace(embedding=vec)])

    return SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        embeddings=SimpleNamespace(create=embeddings_create),
        with_options=lambda **_k: SimpleNamespace(
            responses=SimpleNamespace(create=responses_create)
        ),
    )


def roll_context(handler):
    """A `global_context`-shaped SimpleNamespace over a real `AIHandler` for
    `daily_summary_roll_service._sweep_daily_roll` / `_roll_one_chat_day` — all
    real components (session_manager, roll_marker_store, memory_manager, client,
    config); nothing mocked but the OpenAI boundary inside `handler.client`."""
    return SimpleNamespace(
        session_manager=handler.session_manager,
        ai_handler=handler,
        config=handler.config,
    )


def rolling_config(tmp_path, chat, *, window_days=14):
    return AppConfiguration(
        green_api_instance_id="i", green_api_token="t", ai_api_key="k",
        ai_model="gpt-5.6-luna", ai_reply_max_tokens=500,
        godfather_phone=chat,
        feature_flags={"enable_memory_system": True, "enable_rbac": True},
        data_root=str(tmp_path),
        memory={
            "session": {
                "storage_dir": str(tmp_path / "sessions"),
                "window_days": window_days,
                "max_tokens_by_role": {"client": 4000, "godfather": 100000},
            },
            "longterm": {"enabled": True, "storage_dir": str(tmp_path / "memory"),
                         "daily_summary_top_k": 10},
            "roll": {"hour": 2, "catchup_lookback_days": 21, "stale_claim_minutes": 120},
        },
    )
