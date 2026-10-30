<h1 align="center">Tellers skills</h1>

<p align="center"><strong>Edit videos with your AI agent. Preview and export on your machine.</strong></p>
<p align="center">Cut, layer, title and add effects to local files or URLs, or edit cloud projects with <a href="https://tellers.ai">Tellers</a>.</p>

<table align="center">
<tr><th align="center">Prompt your agent</th></tr>
<tr><td align="center"><pre>Edit videos with https://github.com/tellers-ai/skills</pre></td></tr>
</table>

https://github.com/user-attachments/assets/27b977aa-65b6-4704-99f5-a04dd79f8c7e

[Watch the full demo on YouTube](https://www.youtube.com/watch?v=C1KhD6tU-po)

| Skill | What the agent can do | Needs |
| --- | --- | --- |
| [`video-player`](plugins/video-player/skills/video-player/SKILL.md) | Build OTIO timelines from **local files or URLs** with cuts, layers, titles, effects and music. Preview on `localhost`, edit alongside the assistant in a **full-featured editable timeline**, **export MP4** to the project folder, or move edits between your machine and Tellers with the CLI. | Python 3 + a browser (Chrome / Edge recommended). **No Tellers account.** |
| [`tellers-mcp`](plugins/mcp/skills/tellers-mcp/SKILL.md) | Install the [Tellers MCP](https://mcp.tellers.ai/), edit cloud projects, search footage and transcripts, generate voice, music, images and video, and open a live preview. | A Tellers account (create one on the sign-in page). |

Both use the same timeline format, documented in
[`otio-format.md`](plugins/video-player/skills/video-player/references/otio-format.md).

## Edit alongside your assistant

The `video-player` skill includes the **full-featured Tellers editable timeline**,
the same one used in the Tellers app. Ask your assistant to show the timeline to
trim, split and move clips, edit titles, and adjust effects and transitions while
the preview updates.

Add **markers and notes at precise locations** in the timeline to guide the next
edit. Press **M** to add a marker at the playhead, even during playback, then give
it a name and note. Your edits and feedback are saved locally in OTIO so the
assistant can pick them up and continue from your latest version.

To open it yourself, add `&timeline=1` to the local player URL:
`http://localhost:8000/player.html?otio=timeline.otio&timeline=1`.

## Install

Use the skills CLI as an alternative to the native Claude Code and Codex plugin commands below:

```bash
npx skills add tellers-ai/skills
```

### Claude Code (plugins)

```bash
claude plugin marketplace add tellers-ai/skills
claude plugin install video-player@tellers
claude plugin install mcp@tellers
```

Or from inside Claude Code: `/plugin marketplace add tellers-ai/skills`, then
`/plugin`. The `mcp` plugin also registers the Tellers MCP server; run `/mcp` →
**tellers** → **Authenticate** once to sign in.

No Tellers account yet? The sign-in page has **Continue with Google** and a **Create
account** tab. With an email and password, open the confirmation link Tellers emails
you; the page then unlocks **Approve and continue** on its own. `tellers login`
(Tellers CLI) opens the same page.

### Codex

```bash
codex plugin marketplace add tellers-ai/skills
codex plugin add video-player@tellers
codex plugin add mcp@tellers
```

Or install them from the Plugins directory in the Codex app after adding the
marketplace. The `mcp` plugin registers the Tellers MCP server; sign in with
`codex mcp login tellers`. Codex reads `.agents/plugins/marketplace.json` and each
plugin's `.codex-plugin/plugin.json`; Claude Code reads the `.claude-plugin/` files.
Both use the same `skills/` folders.

### Any agent that reads skill folders

Copy a skill folder into your skills directory: `~/.claude/skills/` for Claude Code,
`~/.agents/skills/` for Codex (or `.agents/skills/` inside a repo):

```bash
cp -R plugins/video-player/skills/video-player ~/.agents/skills/
cp -R plugins/mcp/skills/tellers-mcp ~/.agents/skills/
```

For claude.ai / Claude Desktop, zip a skill folder and upload it under
**Settings → Capabilities → Skills**.

## Layout

```
.claude-plugin/marketplace.json     Claude Code marketplace
.agents/plugins/marketplace.json    Codex marketplace
plugins/
  video-player/
    skills/video-player/
      SKILL.md
      references/otio-format.md      timeline format
      references/transfer-to-tellers.md  local edit -> Tellers project with the CLI
      assets/player.html             full-page player (bundle.js from tellers.ai/videoplayer)
      assets/example.otio
      scripts/serve.py               localhost server with Range + CORS; saves exports
      scripts/check_otio.py          timeline and media URL checker
      scripts/prepare_transfer.py    upload folder for recreating the edit with the Tellers CLI
      scripts/pull_from_tellers.py   Tellers project -> local media + .otio
  mcp/
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
