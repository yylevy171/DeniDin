# Feature 101: Call Green API through the instance's own host, switchable by config

**Status**: Done - implemented and tested, merging to master (not yet released or deployed)
**Priority**: P0 (follow-up to the 2026-10-11 prod outage)
**Branch**: `feature/101-green-api-instance-host`
**Created**: 2026-10-12
**Process**: expedited by explicit operator instruction — no SpecKit pipeline, direct fix

## Why

On 2026-10-11 prod denidin-app could not start. Its startup call
`https://api.green-api.com/waInstance<id>/getSettings/<token>` timed out, the library gave up with
`TypeError: 'NoneType' object is not subscriptable` (`whatsapp_chatbot_python/bot.py:104`), and the
watchdog left the container "Up" with a dead app. The generic host `api.green-api.com`
(`51.250.8.4`) was unreachable from the prod box and from a Mac on another network, from DNS
through TCP (a direct connect to the IP failed; four resolvers agreed on the IP, so not stale DNS).
GREEN-API's own status page listed its site and console as Down.

At the same time the instance's own host answered. From inside the prod container, with the real
prod instance, `https://7107.api.greenapi.com/waInstance710722700252/getStateInstance/<token>`
returned `200 {"stateInstance":"authorized"}` in 0.6 s while the generic host timed out.

Our app never chose a host: the library hardcodes `https://api.green-api.com`
(`whatsapp_chatbot_python/bot.py:33`, `whatsapp_api_client_python/API.py:39`) and nothing in
`src/` overrode it.

## What changes

1. **The API host is derived from the instance id.** `instance_api_host()`
   (`src/utils/green_api_bot.py`) returns `https://<first four digits of the id>.api.greenapi.com`,
   or `None` for an id that is not at least four digits (placeholder/test ids), which leaves the
   library default. Verified for the API host only: `7107.api.greenapi.com` and
   `7105.api.greenapi.com` exist in DNS, `9999.api.greenapi.com` does not.
2. **A config switch, `green_api_host_mode`** (top-level in `config.<env>.json`):
   - `"fixed"` (default when the key is absent) — use the library's shared generic host,
     `https://api.green-api.com`, exactly as before this feature. Deploying this feature changes
     nothing until an environment opts in.
   - `"instance"` — use the derived instance host.
   - Any other value fails `AppConfiguration.validate()` at startup (a typo must not silently pick
     a host).
3. **Optional `green_api_media_host`** (default `null` = library default `media.green-api.com`).
   Passed to the bot as `media`. See "Known gaps".
4. The chosen hosts are logged once at bot construction (`Green API hosts: mode=…, api=…, media=…`).

Single construction site: `GreenAPIMessageSource.connect()` (`src/sources/green_api_source.py`)
passes `host=`/`media=` to `DeniDinGreenAPIBot`, which forwards to the library's `Bot`.
`denidin.py`'s `config_dict` carries both new fields (guard test
`test_every_appconfiguration_field_appears_as_a_config_dict_key` enforces it).

## Switching hosts without a release

`config.<env>.json` is the one config file that is mounted, not baked into the image. To switch an
environment to the instance host: set `"green_api_host_mode": "instance"` in that environment's
`config.<env>.json` and restart the environment. To go back to the generic host: set it to
`"fixed"` (or delete the key) and restart. No new version, no build, in either direction.

The default is `"fixed"`, so **this feature does nothing in an environment until its
`config.<env>.json` is edited to `"instance"`** — the code can be released first and the host
switched afterwards, as a separate config step. Config files are never overwritten by a release.
The config edit itself is an operator action (editing a prod config is not done by an agent).

## What works and what does not (verified, 2026-10-12)

- **Verified live (prod container):** `getStateInstance` on the instance host, 200 `authorized`.
- **Incoming media is unaffected.** Each webhook carries its own `downloadUrl`
  (`denidin.py` reads it; `MediaManager.download_file` does `requests.get(file_url)`); in prod's
  logs every sampled URL (14 of 14) is on `do-media-7107.fra1.digitaloceanspaces.com`, which
  answers TLS from the prod box.
- **Not verified:** the startup call `getSettings`, sending a message, button messages and
  reactions through the instance host. They use the same host and path format as
  `getStateInstance`, but only that one call has been run.

## Known gaps

- **Outgoing file uploads** (`sendFileByUpload`, used only for the fee-agreement `.docx` files,
  `whatsapp_handler.py:212`) go to the media host. The library default `media.green-api.com`
  (`51.250.82.88`) was also unreachable. No per-instance media host exists for 7107:
  `7107.media.greenapi.com` and `7107.media.green-api.com` do not resolve, while `7105.media.*`
  does, and a generic `media.greenapi.com` answers TLS. Which host a 7107 instance should upload
  to is **unconfirmed**; `green_api_media_host` exists so it can be set without a release once
  known. Until then fee-agreement sends are expected to fail while the media host is down.
- The startup path still has no bounded retry: if Green API is unreachable the app crashes at
  `bot.py:104` and relies on the health prober to restart it. Not addressed here.
- Alerting a human on a long Green API outage is Feature 028 FR8.

## Tests

`apps/denidin-app/tests/unit/test_green_api_instance_host.py` (new):
- `instance_api_host`: first-four-digit prefix for real ids; `None` for a placeholder, an empty
  string, fewer than four digits and a non-numeric id; an int id is accepted.
- `GreenAPIMessageSource.connect()` passes the instance host and the media value to the factory;
  `fixed` mode and a placeholder id both pass `host=None`.
- `AppConfiguration`: `green_api_host_mode` defaults to `fixed` (constructor and file), `instance`
  loads from a file, invalid values (`Instance`, `default`, empty, `None`, `True`) fail
  `validate()`; `green_api_media_host` defaults to `None` and loads from a file.
- `tests/unit/test_message_source.py`'s config stub gained the two new attributes.

Full unit + integration run (wrapper, 2026-10-12): 1972 passed, 1 failed.
The failure, `tests/integration/test_end_to_end.py::TestEndToEndFlow::test_send_message_and_verify_response`,
builds its own `GreenAPI(...)` client on the library-default host and calls the live service, so it
fails while `api.green-api.com` is down; it never touches the changed code.

## Acceptance after deploy (human, live)

0. With the default (`fixed`), the startup log shows `Green API hosts: mode=fixed, api=library
   default, …` and behavior is unchanged.
1. With `"green_api_host_mode": "instance"` set and the environment restarted, the startup log shows
   `Green API hosts: mode=instance, api=https://7107.api.greenapi.com, …`.
2. A text message gets a reply; a button approval works; an incoming image/document is processed.
3. Ask for a fee agreement and record what happens (expected to fail until the media host is
   confirmed — see Known gaps).
4. `/health` reports `whatsapp_authorized: success`.

## Out of scope

- Releasing or deploying (version and environment decisions are the operator's).
- Self-healing startup (bounded backoff instead of a one-shot `getSettings`) and prober changes —
  discussed 2026-10-11/12, deliberately not part of this feature.
