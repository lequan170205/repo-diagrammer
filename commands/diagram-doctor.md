---
description: Check which diagram tools are installed and fix what is missing
allowed-tools: Bash, Read
---

Run `bash ${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/check_deps.sh` and report the result.

Then, for this specific repo, say which extraction tools actually matter — there is no
point installing pyreverse for a Go repo. Detect the languages present first, then
recommend only the relevant ones, with the exact install command for the user's
platform.

Call out clearly whether a Mermaid renderer **and** its headless browser are both
available, since a missing browser produces errors that look like syntax failures.
If either is missing, give the one-line fix and note that until it is resolved, every
diagram must be delivered marked as unvalidated.

Offer to run the installs, but do not run them without being asked.
