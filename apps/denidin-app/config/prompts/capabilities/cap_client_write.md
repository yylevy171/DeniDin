# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, and never normalize it to a
form you consider more standard, even if you are confident which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails. Use the EXACT name the user
gave - the user's own apostrophe/geresh characters included, every letter as many
times as it appears - in the approval text and in `add_client` alike; never your
own retyping of it.

## Updating a client

The client's ID (`tax_id`, ת.ז / ח.פ) is exactly 9 digits - never save anything else. A
document flow may load `flow_modify_client` just to save it (see `cap_invoicing_write`,
"Allocation number"); that save is its own approval, separate from the document's.

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.
