# Feature Specification: Processing Multiple Media Images (and Other "Multiple" Requests)

**Feature ID**: 104
**Feature Branch**: `feature/104-multiple-media-images`
**Created**: 2026-10-12
**Status**: Placeholder — not yet specified/clarified. Spun out of Feature 067 (realistic message
handling), which deliberately leaves media out ("media is left out for now" — product owner,
2026-10-12). Run `speckit.specify` + `speckit.clarify` before planning.
**Priority**: P2 (first-pass estimate)
**Depends on**: Feature 067 (the hand-back / pending-user-messages model — no "turn").

## Input

Real-life scenario (product owner, 2026-10-12): **two bank deposit slips sent within about a
second of each other.** More generally, anything the user sends "multiple" of before DeniDin has
answered the first.

## Analysis captured from the Feature 067 session (2026-10-12; code as of that date)

### What happens today (serial, one exchange per image)

- Message handling is serial. Slip 1 goes through the whole path first: download and validation,
  the model, `analyze_media`, post-reply ledger recognition, a reply. Only then is slip 2 handled
  the same way.
- Result: two separate replies and two separate ledger recognitions; slip 2 waits behind slip 1.
  It works, but it is slow, and neither exchange knows about the other.
- In the backbone (Feature 063) media enters through the **same Backbone as text, raw**
  (`denidin.py` `_process_media_message` → `_process_media_message_via_backbone`): it is stored
  at once with its caption, or `[<filename> sent]` when there is none; the file is archived and its
  path saved as the message's `image_path`; the model is told "media attached, not yet extracted"
  and itself decides to `load_capabilities(["cap_media_analysis"])` and call `analyze_media`.

### What would happen if media were simply another message in 067's stream

- Slip 2 would arrive while the model is on slip 1, be stored at once, and be handed to the model
  at the next hand-back with its timestamp.
- The model **could not analyze it**: `analyze_media` works only on the **single raw file attached
  to the current request** (`src/capabilities/media_analysis/handler.py`, `turn_context["media"]`
  = `request.media`), and stores its result against that one message id.

### What would have to change

1. `analyze_media` must be able to **pick any attached file by message id**, loading the already
   archived bytes (the archive path is persisted on the message).
2. The **post-reply ledger recognition** must be confirmed (or changed) to handle **two deposits
   in one stream** — not yet checked.
3. With both done, the model could analyze both slips and answer once, listing both. The
   acceptance scenario would be two slips sent within a second of each other; it is `expensive`
   (two vision calls) and needs its own per-run approval.

### Alternative: keep media serialized

Each image keeps its own exchange, in arrival order — today's behavior. Safer, but two replies and
no coalescing.

### Recommendation recorded at the time

Let media join the stream with `analyze_media` extended to address a specific attached file — it
fits 067's hand-back model and two slips in a row is the real-life case. **Not yet decided by the
product owner**; 067 ships without it.

## Generalization (product owner, 2026-10-12)

"This will be true for every 'multiple' request the user has" — e.g. msg1 "create a combo doc for
X" and msg2 "create a reminder for Y", where msg2 is sent before msg1 is answered. Feature 067
covers only the stream/merge mechanics; whether and how DeniDin should handle **several
independent requests in one stream** (one reply per request? one combined reply? how approvals for
two different writes interact) is an open design question to settle in this feature's
`speckit.clarify`.

## Open questions for `speckit.clarify`

- Media joins the stream with a per-message `analyze_media`, or stays serial per image?
- Multiple independent requests (documents, reminders, ledger events) in one stream: one reply per
  request or one combined reply? How do two pending approvals coexist (the backbone's approval is
  stateless buttons, but the stale-tap guard keys off one `Session.approval_message_id`)?
- Ledger recognition for several media events in one stream.
- `contactsArrayMessage` (several contacts at once) — still declined outright today.
