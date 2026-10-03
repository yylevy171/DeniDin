# Feature 096: Webapp - Undo Client Resolutions

## Overview
Currently, once a client resolution is determined in the webapp, there is no way to go back in the UI if a mistake is made (e.g., matching the wrong name).

## Requirements
- Add a mechanism in the webapp UI to "undo" a client resolution.
- An "undone" name must revert to the "need to resolve" list.
- Ensure the underlying data files (e.g., aliases/resolutions) accurately reflect the removal of the resolution link.
