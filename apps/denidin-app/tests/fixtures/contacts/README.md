# Test Contact Card (vCard) Fixtures

Real-world contact card fixtures for Feature 030 (vCard Contact Card → Client Creation).

## Files

1. **00005372-גיל ברטל .vcf** - Real WhatsApp-shared contact card (vCard 3.0)
   - Name: גיל ברטל (Gil Bartal)
   - Phone: +972 50-795-1824 (`TEL;type=CELL;type=VOICE;waid=972507951824:...`)
   - **No `EMAIL` field** - real WhatsApp contact shares commonly omit email
     entirely, since phone contacts rarely have one saved. This makes the
     "missing mandatory field" case (`user-stories.md` US2 - `add_client`
     needs name/email/phone) the **common** case for this feature, not an
     edge case.
   - Also carries `X-WA-LID` (WhatsApp's internal linked-ID), a
     WhatsApp-specific vCard extension not part of the standard vCard spec -
     not one of the fields this feature maps to `add_client`.
   - Used for: US2 (missing email -> ask before confirming).

2. **complete_card_dana_cohen.vcf** - Synthetic vCard 3.0 (name+phone+email all present),
   since the real fixture above has no email. Used for: US1 (complete card -> confirm ->
   create).

## Notes

- This is a real vCard captured from an actual WhatsApp contact share, not a
  synthetic fixture - the field shape (in particular, no `EMAIL`) should be
  treated as representative of what Green API's `contactMessage` webhook will
  actually carry, superseding the "documented assumption" flagged in
  `specs/backlog/030-vcf-contact-card-client-creation/spec.md`'s
  Clarifications as still needing live confirmation.
