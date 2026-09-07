# Contract C4: Client-resolution gate — `runtime_constitution.md` guidance

**Feature 069** | [plan.md](../plan.md) · [research.md](../research.md) R4/R7 ·
FR-069-010/011/013/014/017/018/033/034/040/041

> **Redesign (2026-09-01).** There is no inline `capture_ledger_event` tool and no
> `record_unresolved_ledger_capture` tool. "The event is captured" now means: **the
> conversation reached a state where the post-turn recognition call
> ([recognition-and-logging.md](./recognition-and-logging.md)) can return `complete`** — i.e.
> every mandatory field for the `source_type` is present, including a `client_name` resolved
> to an exact Morning name. The gate is entirely about **what the conversation must
> establish before that point**.

## Nature of the contract

The gate is **guidance in `config/runtime_constitution.md`, not code** (FR-069-040: no hard
rejection in `LedgerEventManager`, the recognition call, or the ledgerer). This contract
states what the guidance must make the conversational model do. **Exact wording is
UX-impacting (METHODOLOGY §XIX HARD STOP) and is drafted + approved by the operator during
`speckit.implement`** — not committed at plan time.

Client resolution is **ordinary conversation** driven by this guidance and the existing
"Resolving a client by name" flow — never a code state machine, never anything the
recognition call or the ledgerer performs (FR-069-013). The recognition call only *reads*
whether the conversation resolved the client; it never resolves one.

## Placement

A rewrite of the **"Ledger Event Recognition"** section (FR-069-041) with a new subsection
**"אימות לקוח לפני רישום אירוע" ("Client resolution before an event is recorded")**. Plus
bidirectional cross-references (METHODOLOGY §XXI):

- **"Resolving a client by name"** section → add: "This same resolution process is mandatory
  before a `הסכם`, `בנק`, or `חשבונית` ledger event can be considered complete — see 'Client
  resolution before an event is recorded'."
- **"Reminder Management"** section → add to its out-of-scope list: "A ledger-event client
  resolution is not a reminder action."
- **"Invoice Management" / Morning tools** section → the existing "an Invoice Management
  action is automatically 'Neither'" pattern already covers this; add an explicit line that
  the client-resolution sub-step of a ledger recognition is not itself a document-creation
  action.
- Guidance aimed at the **old inline tool** — "call `capture_ledger_event` N times", the
  components-array workaround, "emit the function call before replying" — MUST be **removed**.

## Behavioral requirements the guidance must produce

"Captured" below = "the conversation is in a state the post-turn recognition call will read
as `complete`". No tool call by the conversational model is involved.

| # | Situation | Required model behavior |
|---|---|---|
| G1 | A `הסכם` or `בנק` event is being described (any entry point: typed text, contact-card-framed text, or the synthetic media turn — a `בנק` slip, a photographed `הסכם`, or a `docx` `הסכם`) | Treat the client name as **unresolved** until matched or created against Morning via the **identical** steps as "Resolving a client by name" (`resolve_client_name`, then `add_client` if creating new). Until then the event is not complete — nothing is captured. |
| G2 | `resolve_client_name` returns **exactly one exact match** | **Silent** — no operator question. The event's `client_name` is that exact Morning name; every other provided/extracted field is carried verbatim (from the stash, for media-sourced captures). The event is complete this turn → the recognition call captures it. (FR-069-013) |
| G3 | **One** non-exact / partial candidate | Tell the operator the candidate name **and** offer to create a new client. Capture nothing yet. Wait for their choice. |
| G4 | **2+** partial candidates | List them (short, numbered) **and** offer to create new. Capture nothing yet. Wait for their choice. |
| G5 | **Zero** matches | Proceed to the new-client sub-step (G6). |
| G6 | Creating a new client | Ask for **full name + email + phone** — all three required (message/slip text is a hint only); call `add_client` (its normal approval gate); on success use the newly stored Morning name verbatim. (FR-069-014) |
| G7 | Client resolved (matched or created) | The client-resolution sub-step is done; the event becomes complete once its other mandatory fields (§per-type below) are also present. Resolution is **never the end step** — the end is the event being recorded. (carried-over operator feedback: *not* "ends in create new client") |
| G8 | Operator will not provide email/phone for a new client | Ask — **once**, as a **distinct closed question**, with **no** re-ask for email/phone first — *"should I store this event without full client details, or not?"*. Never default either way. Never volunteer store-anyway before the operator has declined the contact details (or proactively asked for it — G8c). (FR-069-033) |
| G8a | Operator answers **store anyway** | The event completes with `client_name` = the operator-stated name as free text **and** the fixed marker `[לקוח לא אומת במורנינג]` inside `description`. No Morning client is created. All other provided/extracted fields still present. → recognition call returns `complete`. (FR-069-034) |
| G8b | Operator answers **don't store** | Nothing is captured. The recognition call returns `declined` (carrying the stated name + `source_type`); the ledgerer logs one INFO "declined by operator" line. (FR-069-035) |
| G8c | Operator **proactively** elects store-anyway up front (e.g. "תרשום גם בלי אימייל וטלפון" before being asked) | Honour it directly — **no** "בטוח?" / "are you sure?" confirmation turn. Same outcome as G8a. (FR-069-033/034) |
| G9 | Operator's disambiguation reply fits neither a candidate nor "create new" (bare "כן", an unrelated sentence) | Re-ask **once** as an explicit closed choice listing the options. Infer nothing. A second still-ambiguous reply → abandonment: capture nothing, do not guess. (FR-069-018) — cite the constitution's existing "short/ambiguous replies answer the most recently pending question in the same context" rule. |
| G10 | `חשבונית` (in-conversation Morning create) | The client is resolved **by construction** (the `create_*` call succeeded). No separate `resolve_client_name`. The recognition call reads the real Morning response and captures the `חשבונית` event synchronously that turn. (FR-069-012) |
| G11 | `payer_name` on any `הסכם` | **Not** gated — free text, never resolved against Morning. (FR-069-017) |
| G12 | Morning tunnel unavailable during resolution | Resolution cannot complete → the event never becomes complete → nothing is captured with a guessed name. Tell the operator the client could not be verified and to retry. (CONSTITUTION §XVIII — no silent degraded write) |
| G13 | A `בנק` slip that does not clearly name a Morning-resolvable client (an institution/bank name, a third-party payer, or no name at all) | Just the zero-match / hint-only path (G5) — ask the operator who the client is; capture nothing until their answer resolves (or store-anyway is elected). The raw slip string is **never** persisted as `client_name`. No institution-specific rule. (FR-069-013) |
| G14 | The event's other mandatory fields (§per-type) not yet all present, even with the client resolved | Event is not complete — nothing captured. Ask for what's missing, or wait for it, as ordinary conversation. |
| G15 | A correction to an arrangement already resolved earlier in the same conversation | Reuse the previously-resolved exact Morning name — **no** second `resolve_client_name` call. Captured as a fresh event. |
| G16 | One message describes **multiple** events | Each event's client resolves independently; an event is captured the moment *its own* mandatory fields (incl. its client) are complete — so one message can yield a staggered set of captures across turns. (FR-069-016) |
| G17 | The other details of the original request (every `הסכם` fee component, the `בנק` banking triplet, amounts, dates, subtype, `reference`/`reference_hint` established via `query_ledger_events`) | **Never lost** across the resolution detour. The recognition call maps every one of them into the captured event. For media-sourced captures, the stash lines are transcribed verbatim. (FR-069-020/021/022) |

## Per-type mandatory fields the guidance must enforce (before "complete")

Mirrors [data-model.md](../data-model.md) §1 — the guidance must state these so the model
knows *when* an event is complete, not just that the client must resolve:

- **`הסכם`**: resolved `client_name` (or store-anyway); event date; `description`; ≥1 fee
  component OR a number of hours. Per component: `amount` > 0 OR `percent`.
- **`בנק`**: resolved `client_name` (or store-anyway); `txn_date`; `amount`; `description`;
  `vat_status` (`כולל` unless the operator explicitly states otherwise).
- **`חשבונית`**: `client_name` (resolved by construction); `txn_date`; `event_subtype` (the
  document type); `amount`; `accounting_document_display_number` — all from the real Morning
  response.

## `reference` / `reference_hint`

Retain-if-provided for **all** source types. Established **in conversation** by the model,
which may call `query_ledger_events` (read-only, still attached) to find the related prior
event. The guidance must state: the model never *creates* a ledger event to establish a
link; it only searches. The recognition call carries whatever link the conversation
established into the captured event; the ledgerer denormalizes an already-decided
`reference` id into display fields but never *decides* the link. (FR-069-021)

## No feature flag

Per the 2026-08-31 operator direction, this feature has no `config.feature_flags` toggle and
no config key. The constitution guidance and the code land in the **same PR**; the only gate
before it reaches an environment is the normal explicit human deploy (merge ≠ redeploy),
backed by a green billed/expensive acceptance run.

## Tests

- Behavior G1–G17 is exercised by the **billed/expensive acceptance suite** (real OpenAI +
  real Morning sandbox) — see `user-stories.md` and
  `contracts/payload-fidelity-manifest.md`. Mapping: US4/US5 (G3–G6 typed `הסכם`), US6 (G2),
  US7 (G2–G6 via a `בנק` image — 7a/7b/7c cover the three non-exact match-counts, 7d covers
  the silent exact-match path G2/G13), US8 (G8/G8a/G8b/G8c), US9 (G3–G6 photographed `הסכם`),
  US10 (G3–G6 `docx` `הסכם`), US2 (G10), US3 (no misfire).
- No unit test asserts constitution wording.
- The acceptance suite runs against `config.test.json`.
