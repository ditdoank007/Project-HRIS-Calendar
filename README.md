# HRIS Reborn Calendar

Calendar Portal for HRIS Reborn.

## Server

- SERVER-CALENDAR
- CT133

## Runtime

- Python 3.13.5
- Flask 3.1.3
- Gunicorn 26.2.0
- systemd

## Application

Entry point: `app.py`

Configuration: `config.py`

Runtime environment: `/opt/calendar/.env`

## Main Endpoints

- `/`
- `/api/login`
- `/dashboard`
- `/calendar`
- `/phone-calendar`
- `/agenda`
- `/plans`
- `/api/phone-calendar-info`
- `/api/personal-calendar`
- `/api/calendar/<token>.ics`
- `/api/logout`
- `/health`

## Integration

- BDIP SSO
- HRIS Internal API
- Personal Calendar
- ICS Calendar Feed

## Deployment

Systemd service: `systemd/calendar.service`

Production working directory: `/opt/calendar/app`

Gunicorn: `/opt/calendar/venv/bin/gunicorn`

Production binding: `0.0.0.0:80`

## Dependencies

Production Python dependencies are pinned in `requirements.txt`.

## Security

Secrets are loaded from environment variables.

Never commit `.env`, passwords, API keys, session secrets, authentication tokens, or private keys.

Backup files and virtual environments are excluded through `.gitignore`.
