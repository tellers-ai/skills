# skills

Tellers skills to be used by AI agents like Claude Code, OpenClaw, Codex, Claude Cowork, Paperclip, etc.

## Skills

Skills live in the `skills/` directory. Each skill has its own folder containing a `SKILL.md` file.

| Skill | Description | Published |
|-------|-------------|-----------|
| [use-tellers](skills/use-tellers/) | Use the Tellers CLI to upload, edit, and generate videos (real footage or AI-generated) | [clawhub.ai/yxdunc/tellers](https://clawhub.ai/yxdunc/tellers) |
| [integrate-tellers](skills/integrate-tellers/) | Integrate Tellers into a codebase via the REST API | — |

## Packaging a skill

A `.skill` file is a ZIP archive containing a `SKILL.md` file inside a folder named after the skill.

```bash
cd skills/<skill-name>
zip -r ../../<skill-name>.skill .
```

Example:
```bash
cd skills/use-tellers
zip -r ../../use-tellers.skill .
# produces: use-tellers.skill (ZIP containing use-tellers/SKILL.md)
```

## Publishing on ClawHub

1. Package the skill as described above.
2. Go to [clawhub.ai](https://clawhub.ai) and sign in.
3. Upload the `.skill` file to publish or update the skill.
4. The published URL follows the pattern `clawhub.ai/<username>/<skill-name>`.
