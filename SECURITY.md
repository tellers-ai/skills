# Security

## Reporting a vulnerability

Please do not open a public issue. Report it privately from this repository's
**Security** tab → **Report a vulnerability**, with the details and, if you can, steps
to reproduce. We will acknowledge within a few working days.

## What this repository contains

Agent skills and plugin manifests only: Markdown, JSON and small standard-library
Python scripts. It holds no credentials. The Tellers MCP signs in with OAuth in your
client, and the scripts read `TELLERS_API_KEY` or the `tellers login` session from your
machine at run time; neither is ever written to this repository.

`scripts/serve.py` listens on `127.0.0.1` by default, answers CORS only for
`localhost` pages and rejects non-localhost `Host` headers. With `--host 0.0.0.0`
everyone on your network can read the folder you serve, so serve only a folder that
holds the edit.
