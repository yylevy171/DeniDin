# Default personality

No named personality matches this directory. This should never happen — every
active window is expected to be running from either the `coder1` or `coder2`
worktree, each with its own dedicated personality file.

If you are reading this, stop and tell the user immediately: the current
working directory does not match any known personality (`coder1`/`coder2`),
which means the setup is misconfigured or a window is pointed at the wrong
folder (e.g. the original clone, or a stray/incorrectly-named worktree).
Do not silently proceed as if this were normal.
