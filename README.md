# skills

Tellers skills to be used by AI agents like Claude Code, OpenClaw, Codex, Claude Cowork, Paperclip, etc.

## Skills

Skills live in the `skills/` directory. Each skill has its own folder containing a `SKILL.md` file.

| Skill | Description | Published |
|-------|-------------|-----------|
| [use-tellers](skills/use-tellers/) | Use the Tellers CLI to upload, edit, and generate videos (real footage or AI-generated) | [clawhub.ai/yxdunc/tellers](https://clawhub.ai/yxdunc/tellers) |
| [integrate-tellers](skills/integrate-tellers/) | Integrate Tellers into a codebase via the REST API | — |

## Installation

Install these skills using the [skills CLI](https://skills.sh/docs):

```sh
npx skills add tellers-ai/skills
```

## Publishing on ClawHub

1. Go to [clawhub.ai](https://clawhub.ai) and sign in.
2. Upload the skill to publish or update it.
3. The published URL follows the pattern `clawhub.ai/<username>/<skill-name>`.
