# Tellers skills

Skills that let AI agents (Claude Code, Codex, Claude Desktop, Cursor and any agent
that reads `SKILL.md` folders) edit video with [Tellers](https://tellers.ai): cut a
montage from local files or URLs and preview and export it in the Tellers player on
your machine, or edit your Tellers projects in the cloud through the Tellers MCP.

| Skill | What the agent can do | Needs |
| --- | --- | --- |
| [`tellers-otio-player`](plugins/tellers-otio-player/skills/tellers-otio-player/SKILL.md) | Write a Tellers OTIO timeline from **local files and/or internet URLs** (cuts, layers, titles, effects, music), play it in the Tellers player on `localhost`, and **export it to MP4** into the project folder. Also moves an edit to Tellers with the CLI, and pulls a Tellers project back to local files. | Python 3 and a browser (Chrome / Edge recommended). No account. |
| [`tellers-mcp`](plugins/tellers-mcp/skills/tellers-mcp/SKILL.md) | **Install the Tellers MCP** (`https://mcp.tellers.ai/`) in Claude Code, Claude Desktop, Codex or Cursor, then edit Tellers projects, search footage and transcripts, generate voice, music, images and video, and open a live preview. | A Tellers account. |

Both use the same timeline format, documented in
[`otio-format.md`](plugins/tellers-otio-player/skills/tellers-otio-player/references/otio-format.md).

## Install

### Claude Code (plugins)

```bash
claude plugin marketplace add tellers-ai/skills
claude plugin install tellers-otio-player@tellers
claude plugin install tellers-mcp@tellers
```

Or from inside Claude Code: `/plugin marketplace add tellers-ai/skills`, then
`/plugin`. The `tellers-mcp` plugin also registers the Tellers MCP server; run `/mcp` →
**tellers** → **Authenticate** once to sign in.

### Codex

```bash
codex plugin marketplace add tellers-ai/skills
codex plugin add tellers-otio-player@tellers
codex plugin add tellers-mcp@tellers
```

Or install them from the Plugins directory in the Codex app after adding the
marketplace. The `tellers-mcp` plugin registers the Tellers MCP server; sign in with
`codex mcp login tellers`. Codex reads `.agents/plugins/marketplace.json` and each
plugin's `.codex-plugin/plugin.json`; Claude Code reads the `.claude-plugin/` files.
Both use the same `skills/` folders.

### skills CLI

```bash
npx skills add tellers-ai/skills
```

### Any agent that reads skill folders

Copy a skill folder into your skills directory: `~/.claude/skills/` for Claude Code,
`~/.agents/skills/` for Codex (or `.agents/skills/` inside a repo):

```bash
cp -R plugins/tellers-otio-player/skills/tellers-otio-player ~/.agents/skills/
cp -R plugins/tellers-mcp/skills/tellers-mcp ~/.agents/skills/
```

For claude.ai / Claude Desktop, zip a skill folder and upload it under
**Settings → Capabilities → Skills**.

## Layout

```
.claude-plugin/marketplace.json     Claude Code marketplace
.agents/plugins/marketplace.json    Codex marketplace
plugins/
  tellers-otio-player/
    skills/tellers-otio-player/
      SKILL.md
      references/otio-format.md      timeline format
      references/transfer-to-tellers.md  local edit -> Tellers project with the CLI
      assets/player.html             full-page player (bundle.js from tellers.ai/videoplayer)
      assets/example.otio
      scripts/serve.py               localhost server with Range + CORS; saves exports
      scripts/check_otio.py          timeline and media URL checker
      scripts/prepare_transfer.py    upload folder for recreating the edit with the Tellers CLI
      scripts/pull_from_tellers.py   Tellers project -> local media + .otio
  tellers-mcp/
    .mcp.json                        registers https://mcp.tellers.ai/ (both agents)
    skills/tellers-mcp/SKILL.md
    skills/tellers-mcp/agents/openai.yaml  Codex metadata + MCP dependency
```

## The player

The player is `bundle.js` (`TellersPlayerUI`), the same player that ships in
the Tellers app, published at `https://tellers.ai/videoplayer/bundle.js`.
Workers, codecs and assets are inlined, so pages on any origin load it with one
`<script>` tag. `player.html?src=<url>` tries another build. Playback, export and
subject detection run in the browser, so they depend on that machine; detection
(`detect`, outline masks) needs a GPU to run at a usable speed.

## License

MIT. See [LICENSE](LICENSE).
