"""Single source of truth for a chat's long-term-memory ChromaDB collection name
(Feature 070).

Before this module the name was constructed ad-hoc in three places in
`ai_handler.py` as ``f"memory_{chat.replace('@c.us','')}"``, and one of those
call sites then did a raw ``client.get_collection(...)`` with the *unsanitised*
name - which threw ``NotFoundError`` for group chats (``…@g.us``) because the
raw ``@`` never matched the collection ChromaDB had actually stored under the
sanitised ``…_at_g.us`` name. That was bugfix-035 H1, and Feature 070 removes it
structurally: every path that needs the name calls `collection_name_for_chat`,
and nothing calls `client.get_collection` with a raw chat id.

The algorithm reproduces the names ChromaDB already holds in production
(verified live 2026-09-02):

    972522968679@c.us        -> memory_972522968679
    120363210094632983@g.us  -> memory_120363210094632983_at_g.us

i.e. the historical two-step: ``memory_{chat.replace('@c.us','')}`` then the
``MemoryManager.get_or_create_collection`` inline sanitiser
``.replace('@','_at_').replace(':','_')``.
"""


def collection_name_for_chat(whatsapp_chat: str) -> str:
    """Return the ChromaDB collection name for a chat's long-term memory.

    Works for every chat-id shape (``@c.us``, ``@g.us``, ``@lid``, anything
    else) and never raises - the two ``.replace`` calls make any remaining
    ``@`` / ``:`` collection-name-safe.
    """
    base = "memory_" + whatsapp_chat.replace("@c.us", "")
    return base.replace("@", "_at_").replace(":", "_")
