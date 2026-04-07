---
name: tellers_integrate
description: "Integrate Tellers.ai into a codebase using the REST API or SDK — covers authentication, uploading media, generating videos, polling status, and handling results programmatically. Use when a user wants to call the Tellers API from their app, script, or backend service. Triggers on phrases like 'integrate tellers', 'tellers API', 'call tellers from my code', 'tellers SDK', 'tellers in my app', 'programmatic video generation', 'tellers REST API'."
---

# Tellers Integration Skill

This skill guides you through integrating [Tellers.ai](https://www.tellers.ai) into a codebase via its REST API.

Full API reference: https://www.tellers.ai/docs/dev/api

## Authentication

All requests require a bearer token. Obtain an API key from [app.tellers.ai](https://app.tellers.ai) → user menu → API keys → Create new.

```
Authorization: Bearer sk_...
```

Store the key in an environment variable (`TELLERS_API_KEY`), never hard-code it.

## Base URL

```
https://api.tellers.ai
```

## Core Workflows

### 1. Upload Media

**POST** `/upload/v1/upload`

Multipart form upload. Returns an `asset_id` for use in generation.

```python
import os, requests

def upload_file(path: str) -> str:
    with open(path, "rb") as f:
        resp = requests.post(
            "https://api.tellers.ai/upload/v1/upload",
            headers={"Authorization": f"Bearer {os.environ['TELLERS_API_KEY']}"},
            files={"file": f},
        )
    resp.raise_for_status()
    return resp.json()["asset_id"]
```

```typescript
import fs from "fs";
import FormData from "form-data";
import fetch from "node-fetch";

async function uploadFile(path: string): Promise<string> {
  const form = new FormData();
  form.append("file", fs.createReadStream(path));
  const res = await fetch("https://api.tellers.ai/upload/v1/upload", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.TELLERS_API_KEY}`,
      ...form.getHeaders(),
    },
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json() as { asset_id: string };
  return data.asset_id;
}
```

### 2. Generate a Video

**POST** `/agent/v1/chat`

Send a natural-language prompt. Optionally reference uploaded assets by ID.

```python
import os, requests

def generate_video(prompt: str, asset_ids: list[str] = []) -> dict:
    payload = {
        "message": prompt,
        "asset_ids": asset_ids,   # optional: reference uploaded footage
    }
    resp = requests.post(
        "https://api.tellers.ai/agent/v1/chat",
        headers={
            "Authorization": f"Bearer {os.environ['TELLERS_API_KEY']}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()  # { chat_id, message, status, projects, assets }
```

```typescript
async function generateVideo(prompt: string, assetIds: string[] = []) {
  const res = await fetch("https://api.tellers.ai/agent/v1/chat", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.TELLERS_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message: prompt, asset_ids: assetIds }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json(); // { chat_id, message, status, projects, assets }
}
```

### 3. Poll Asset / Project Status

**GET** `/asset/v1/asset/{id}`

Use this to check when an upload has finished processing or when a generated project is ready.

```python
import time

def wait_for_asset(asset_id: str, interval: int = 5, timeout: int = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"https://api.tellers.ai/asset/v1/asset/{asset_id}",
            headers={"Authorization": f"Bearer {os.environ['TELLERS_API_KEY']}"},
        )
        resp.raise_for_status()
        asset = resp.json()
        if asset["status"] in ("analysed", "done", "ready"):
            return asset
        time.sleep(interval)
    raise TimeoutError(f"Asset {asset_id} not ready after {timeout}s")
```

### 4. Export a Project to MP4

**POST** `/project/v1/project/{id}/export`

Renders the project to a downloadable MP4. Returns a new `asset_id` for the export.

```python
def export_project(project_id: str) -> str:
    resp = requests.post(
        f"https://api.tellers.ai/project/v1/project/{project_id}/export",
        headers={"Authorization": f"Bearer {os.environ['TELLERS_API_KEY']}"},
    )
    resp.raise_for_status()
    return resp.json()["asset_id"]
```

### 5. Make an Asset Public

**PUT** `/asset/v1/asset/{id}/anonymous-read`

Required before sharing a preview link.

```python
def make_public(asset_id: str) -> str:
    requests.put(
        f"https://api.tellers.ai/asset/v1/asset/{asset_id}/anonymous-read",
        headers={"Authorization": f"Bearer {os.environ['TELLERS_API_KEY']}"},
    ).raise_for_status()
    return f"https://www.tellers.ai/preview/{asset_id}"
```

## End-to-End Example

```python
import os, requests, time

API_KEY = os.environ["TELLERS_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# 1. Upload
with open("footage.mp4", "rb") as f:
    asset_id = requests.post(
        "https://api.tellers.ai/upload/v1/upload",
        headers=HEADERS, files={"file": f}
    ).raise_for_status() or ...  # simplified

# 2. Wait for analysis
# (poll /asset/v1/asset/{asset_id} until status == "analysed")

# 3. Generate
result = requests.post(
    "https://api.tellers.ai/agent/v1/chat",
    headers={**HEADERS, "Content-Type": "application/json"},
    json={"message": "Create a 60s highlight reel", "asset_ids": [asset_id]},
).json()
project_id = result["projects"][0]

# 4. Export
export_asset_id = requests.post(
    f"https://api.tellers.ai/project/v1/project/{project_id}/export",
    headers=HEADERS,
).json()["asset_id"]

# 5. Share
requests.put(
    f"https://api.tellers.ai/asset/v1/asset/{export_asset_id}/anonymous-read",
    headers=HEADERS,
)
print(f"https://www.tellers.ai/preview/{export_asset_id}")
```

## App Deep Links

```
# View asset in app:
https://app.tellers.ai/?asset_id={asset_id}

# View project in app (with chat context):
https://app.tellers.ai/?asset_id={project_id}&chat_id={chat_id}

# Public shareable preview (no login required):
https://www.tellers.ai/preview/{asset_id}
```

## Error Reference

| HTTP Status | Meaning |
|-------------|---------|
| 401 | Invalid or missing API key |
| 402 | Insufficient credits — top up at app.tellers.ai |
| 422 | Invalid request payload |
| 5xx | Server error — retry with backoff |

## Further Resources

- Full API docs: https://www.tellers.ai/docs/dev/api
- OpenAPI spec: `src/tellers_api/openapi.tellers_public_api.yaml` in the CLI repo
- CLI source (reference implementation): https://github.com/tellers-ai/tellers-cli
- Support: Discord https://discord.gg/sGg2fnmfCr
