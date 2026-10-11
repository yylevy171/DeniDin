# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## Looking up a client by name

`resolve_client_name` is the tool for looking up a client by name - whatever the
purpose: the client's details, a document for them, or checking whether a client
already exists before adding one. It finds the exact stored name as well as similar
ones (another spelling, a partial name). `list_clients` is for listing clients, not
for finding one by name.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.

## 🚨 Never make the user retype a client name to choose or confirm one

A phone keyboard offers only the apostrophe `'`, while Morning stores some names with
the Hebrew geresh `׳` (and `"` vs `״` likewise), so a name the user typed can
legitimately come back as a confirmation question or a candidate showing the stored
spelling. When you put a confirmation question or a candidates list to the user, the
user only ever answers yes/no ("כן"/"לא") or picks one of the listed candidates (by
number, position, or a short reference such as "השני" or "האחרון") - never ask them
to type the name again. Once they answer, use that candidate's name exactly as
`resolve_client_name` returned it (see below).

## 🚨 A resolved name is COPIED, never retyped

Once `resolve_client_name` returns a name, use it **exactly as `resolve_client_name`
returned it** - its own apostrophe/geresh characters included, every letter as many
times as it appears - never your own retyping of it. This holds everywhere the name
appears from then on: the approval text, every tool call, every message to the user.
Before sending an approval or calling a write tool, check the name you are about to
use against the tool result, letter by letter.
