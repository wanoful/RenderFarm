# RenderFarm

A self-hosted Blender render farm with HTTP Basic Auth, safe output isolation, and a Blender addon client.

## Architecture

```
Blender Addon (submit)  →  FastAPI Server (queue)  →  Worker (render GPU)
       ↓                         ↓                          ↓
   RFAddon/                  server/                    worker/
```

## Quick Start

### 1. Install Blender

`worker/blender_runner.py` searches these paths for Blender:

```
/home/wano/Tools/blender-5.1.2-linux-x64/blender
/home/wano/Art/RenderFarm/blender-5.1.2-linux-x64/blender
/usr/bin/blender
/usr/local/bin/blender
```

Edit `BLENDER_PATHS` in `worker/blender_runner.py` to add your own paths.

### 2. Configure users

Edit `config/users.yaml`:

```yaml
users:
  admin: your-password-here
  collaborator: their-password
```

### 3. Start server

```bash
cd server && uv sync && uv run python main.py
```

The server listens on `http://0.0.0.0:8000` by default. Edit `main.py` to change host/port.

### 4. Start worker

```bash
cd worker && uv sync
RENDERFARM_USER=admin RENDERFARM_PASS=your-password-here uv run python main.py
```

Environment variables:
- `RENDERFARM_SERVER` — server URL (default: `http://10.80.73.62:8000`)
- `RENDERFARM_USER` — worker auth username
- `RENDERFARM_PASS` — worker auth password
- `RENDERFARM_WORKER` — worker name (default: `worker1`)
- `RENDERFARM_TMP` — temp directory (default: `/tmp/renderfarm-worker`)

### 5. Install Blender addon

Copy `RFAddon/` to `~/.config/blender/<version>/scripts/addons/RFAddon/`, then enable it
in Blender: Edit > Preferences > Add-ons > RenderFarm.

In the addon preferences, set:

| Setting     | Value                     |
|-------------|---------------------------|
| Server URL  | `http://server-ip:8000`   |
| Username    | Your username             |
| Password    | Your password             |

### 6. Submit a job

1. Open a .blend file
2. Go to Output Properties > RenderFarm panel
3. Click **Submit to Farm**
4. Enter job name, confirm frame range
5. Click **Refresh** to monitor progress
6. Click **Download** when complete

## Systemd (production)

```bash
sudo cp renderfarm-server.service renderfarm-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now renderfarm-server renderfarm-worker
```

Edit `renderfarm-worker.service` to set your credentials in `Environment=`.

## API

All endpoints require HTTP Basic Auth.

| Method   | Path                        | Description              |
|----------|-----------------------------|--------------------------|
| GET      | `/api/health`               | Health check (no auth)   |
| GET      | `/api/auth/login`           | Verify credentials       |
| GET      | `/api/jobs`                 | List your jobs           |
| POST     | `/api/jobs`                 | Submit a job             |
| GET      | `/api/jobs/{id}`            | Job status + chunks      |
| GET      | `/api/jobs/{id}/output`     | Download rendered output |
| DELETE   | `/api/jobs/{id}`            | Cancel (running) or delete (finished) |
| POST     | `/api/jobs/claim`           | Worker: claim a chunk    |
| PUT      | `/api/jobs/{id}/chunks/{cid}` | Worker: update chunk    |
| POST     | `/api/jobs/{id}/frames`     | Worker: upload frames    |
| GET      | `/api/jobs/{id}/files/{fn}` | Worker: download blend   |

## Path Safety

Unlike Flamenco, submitters have no control over output paths. The server assigns
`shared-storage/<job_id>/` for every job. Workers only write to paths the server
tells them to.
