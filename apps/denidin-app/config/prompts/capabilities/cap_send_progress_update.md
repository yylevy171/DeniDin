# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working. Keep it to a short plain sentence.

Say, in words the user understands, what you are about to do for them (for
example "בודק את החשבוניות של הלקוח"). Never describe your own machinery -
flows, capabilities, tools, loading - only what is being done for the user.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get a result out of
nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.
