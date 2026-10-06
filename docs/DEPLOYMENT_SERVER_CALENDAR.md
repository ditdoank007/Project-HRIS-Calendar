# HRIS-Calendar — Deployment & Server Reference

> **Purpose:** single source of truth for ChatGPT and administrators when continuing HRIS-Calendar work in a new chat.
>
> **Important:** Before giving deployment/pull/restart CLI commands, read this file first. Do not assume the Git working tree is `/opt/calendar`.

## 1. Repository

- Repository: `ditdoank007/Project-HRIS-Calendar`
- Active development branch: `feature/pengajuanku-sidebar`
- GitHub is the source of truth for application code.
- Permanent code changes must be committed and pushed to GitHub first.
- Production/server changes should normally be performed by pulling the intended branch from GitHub.

## 2. Production Server

- Hostname: `SERVER-CALENDAR`
- Application root: `/opt/calendar`
- Git working copy: **`/opt/calendar/app`**
- Python virtual environment: `/opt/calendar/venv`
- Environment file: `/opt/calendar/.env`
- Systemd service: `calendar.service`

### Critical path distinction

The following are different directories:

```text
/opt/calendar
├── .env
├── venv/
└── app/          <-- THIS IS THE GIT REPOSITORY AND APPLICATION WORKING TREE
    └── .git/
```

Therefore:

- `cd /opt/calendar` is **not** a Git repository.
- `cd /opt/calendar/app` is the Git repository.
- Never run `git pull` from `/opt/calendar`.
- Do not create a new `.git` directory under `/opt/calendar`.
- Do not clone another copy unless the deployment architecture has explicitly changed.

## 3. Systemd Service

Current service definition:

```ini
[Unit]
Description=HRIS Reborn Calendar Portal
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/calendar/app
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/calendar/venv/bin/gunicorn \
    --bind 0.0.0.0:80 \
    --workers 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Runtime facts

- Gunicorn executable: `/opt/calendar/venv/bin/gunicorn`
- Bind address: `0.0.0.0:80`
- Workers: 2
- Timeout: 60 seconds
- WSGI target: `app:app`
- Working directory: `/opt/calendar/app`

## 4. Privilege Model

The current production service runs as `root`, and the server environment does **not** have the `sudo` command installed.

Therefore, when logged in as `root`, use `systemctl` directly:

```bash
systemctl restart calendar.service
systemctl status calendar.service --no-pager
```

Do **not** prefix commands with `sudo` on this server.

## 5. Standard Deployment Procedure

When GitHub contains the required change:

```bash
cd /opt/calendar/app

git status
git branch --show-current
git log -1 --oneline

git pull origin feature/pengajuanku-sidebar

systemctl restart calendar.service
systemctl status calendar.service --no-pager

journalctl -u calendar.service -n 80 --no-pager
```

If `git status` shows local modifications, **stop before pulling** and inspect them. Do not overwrite or discard production changes blindly.

After deployment, verify the running process:

```ps -ef
grep```

Use:

```bash
ps -ef | grep -E "gunicorn|calendar" | grep -v grep
```

Expected executable:

```text
/opt/calendar/venv/bin/gunicorn
```

## 6. Mandatory Diagnostics Before Giving Deployment CLI

If there is any uncertainty about the server layout, run these commands first:

```bash
cd /opt/calendar

pwd
ls -la

systemctl cat calendar.service --no-pager

find /opt/calendar -maxdepth 3 -type d -name ".git" -print

ps -ef | grep -E "gunicorn|calendar" | grep -v grep
```

Do not infer the Git path from the application root. Read `WorkingDirectory`, `ExecStart`, and the actual `.git` location.

## 7. Configuration

The application root has:

```text
/opt/calendar/.env
```

The application code is under:

```text
/opt/calendar/app
```

The virtual environment is:

```text
/opt/calendar/venv
```

Do not commit production secrets from `.env` to GitHub.

## 8. Current HRIS Internal API Integration

HRIS-Calendar communicates with HRIS Reborn through the internal API.

Relevant Calendar environment/configuration:

- `HRIS_INTERNAL_API_URL`
- `HRIS_INTERNAL_API_KEY`

The Calendar application loads configuration from `/opt/calendar/.env`.

For Rekam Medisku, Calendar proxies:

```text
GET /api/rekam-medisku
        |
        v
HRIS_INTERNAL_API_URL
        |
        v
/api/internal/calendar/rekam-medis/history
```

Calendar sends:

```text
X-Calendar-Internal-Key
X-Calendar-NIP
```

The browser-facing Calendar endpoint requires the logged-in user's session/NIP.

## 9. Current Rekam Medisku Deployment State

The feature is implemented on branch:

```text
feature/pengajuanku-sidebar
```

Relevant application pieces:

- `app.py`
  - `/rekam-medisku`
  - `/api/rekam-medisku`
- `templates/dashboard.html`
  - sidebar menu `REKAM MEDISKU`
  - history table
  - detail modal
  - JavaScript API loading
- `static/css/dashboard.css`
  - Rekam Medisku history/detail UI styles

Recent GitHub commits:

- `32603355a2b37b27a47c5794ad3e50e4f5929dde`
  - `fix: separate rekam medisku sidebar menu`
- `fc33855d58f4830ddc384131ed514b358ec87038`
  - `style: add Rekam Medisku history and detail UI`

## 10. HRIS Backend Dependency

HRIS Reborn repository:

```text
ditdoank007/Project-HRIS
```

HRIS branch currently used for this project:

```text
feature/uang-siaga-v2
```

HRIS server:

```text
SERVER-HRIS
/opt/hris/app
```

The HRIS Rekam Medis internal history endpoint is:

```text
/api/internal/calendar/rekam-medis/history
```

This endpoint has already been verified on SERVER-HRIS with HTTP 200 and valid Dityo Mahendro Rekam Medis data.

Relevant HRIS fix commit:

- `f2876c04b47a7b9f4363aafec4a3fc729b6d34fe`
  - `fix: import calendar rekam medis history route`

## 11. Current Verified Rekam Medis Data Flow

A known test employee:

```text
NIP: 198008292010121001
Nama: DITYO MAHENDRO, S.Kom., M. M.
```

HRIS internal API was verified returning:

- status: `success`
- total: 1
- kegiatan_id: 3
- rekam_id: 1
- tanggal kegiatan: `2026-10-13`
- jam: `08:00`
- hasil kebugaran: `FIT`
- tekanan darah: `120/80`
- nadi: `70`
- frekuensi nafas: `18`
- suhu: `36.0`
- SpO2: `98`
- keluhan: `Pusing`
- pemeriksa: `RIADIMA TRUBUS YANROZIR, A.Md.`

Therefore, if Calendar shows no data, first distinguish:

1. Calendar deployment/code problem
2. Calendar session/NIP problem
3. Calendar environment/API-key problem
4. HRIS upstream API problem

Do not immediately modify HRIS if the HRIS endpoint itself is already verified.

## 12. New Chat Operating Rule

When a new HRIS-Calendar chat starts, use this file as the first deployment reference.

Before producing a CLI command, establish:

1. repository name
2. branch
3. server hostname
4. application root
5. Git working directory
6. virtualenv path
7. systemd service
8. systemd WorkingDirectory
9. systemd ExecStart
10. relevant environment file
11. upstream API dependency

If these facts are already documented here and no server evidence indicates a change, use the documented values instead of guessing.

If a command fails because the documented architecture appears to have changed, inspect the server and then update this file in GitHub so the same mistake is not repeated in future chats.

## 13. Do Not Do This

Never blindly run:

```bash
cd /opt/calendar
git pull ...
```

Never blindly:

- create `.git` under `/opt/calendar`
- clone a second repository into `/opt/calendar`
- change systemd paths without checking the existing service
- overwrite `.env`
- discard local production changes with `git reset --hard`
- restart a service before confirming the deployed working tree

## 14. Quick Reference

| Item | Value |
|---|---|
| Repository | `ditdoank007/Project-HRIS-Calendar` |
| Branch | `feature/pengajuanku-sidebar` |
| Server | `SERVER-CALENDAR` |
| App root | `/opt/calendar` |
| Git repo | `/opt/calendar/app` |
| WorkingDirectory | `/opt/calendar/app` |
| Venv | `/opt/calendar/venv` |
| Env | `/opt/calendar/.env` |
| Service | `calendar.service` |
| Gunicorn | `/opt/calendar/venv/bin/gunicorn` |
| Port | `80` |
| WSGI | `app:app` |
| HRIS upstream | `HRIS_INTERNAL_API_URL` |
| Rekam Medis endpoint | `/api/internal/calendar/rekam-medis/history` |
