# PiDeploy

PiDeploy is a Raspberry Pi deployment tool for a small home server stack. It includes a Python desktop app, Docker Compose services, Glance dashboard config, dashboard assets, and helper scripts for Steam achievement widgets.

The main goal is simple: manage the Pi from your desktop without typing the same SSH and Docker commands every time.

## What This Includes

- A desktop deployment app: `deploy_tool.py`
- A Raspberry Pi setup script: `setup_pi_stack.sh`
- A Docker Compose stack: `docker_compose.yaml`
- Glance dashboard config: `glance/config/`
- Glance images, icons, CSS, and custom API scripts: `glance/assets/`
- Website deployment controls for Node sites
- Discord bot deployment controls for Node bots
- Uptime Kuma backup and restore controls
- Docker service controls for starting, stopping, restarting, and checking containers
- Hardware monitor deployment support through a systemd service

## Services

The Docker stack includes these services by default.

### Uptime Kuma

Uptime Kuma runs on port `3001`.

Use it to monitor websites, services, devices, and local endpoints.

Default URL:

```text
http://PI_IP:3001
```

### Glance

Glance runs on port `8080`.

Use it as the main dashboard for links, feeds, server stats, Reddit, YouTube, weather, Steam data, and other widgets.

Default URL:

```text
http://PI_IP:8080
```

### Steam Achievements API

This is a small Python API used by the Glance gaming page.

It provides:

- `/health`
- `/recent-achievements?limit=10`
- `/weekly-challenge?count=3`

The API reads Steam settings from environment variables in `docker_compose.yaml`:

- `STEAM_API_KEY`
- `STEAM_ID`
- `PORT`
- `TZ`

Create a `.env` file next to the Docker Compose file on the Pi:

```text
/srv/docker/compose/core/.env
```

Use this format:

```text
STEAM_API_KEY=your-steam-api-key
STEAM_ID=your-steam-id
```

The repo includes `.env.example` as a template. Do not commit your real `.env` file.

### Node Websites

The deploy tool can upload local Node website folders to the Pi and add Docker Compose service blocks for them.

Website files are uploaded to:

```text
/srv/docker/data/websites/
```

Each website can have one or more Node entry files, host ports, and container ports.

### Discord Bots

The deploy tool can upload local Node Discord bot folders to the Pi and run them as Docker Compose services.

Bot files are uploaded to:

```text
/srv/docker/data/discord-bots/
```

Each bot can have one or more Node entry files.

## Folder Layout

```text
.
|-- deploy_tool.py
|-- deploy_tool_settings.json
|-- docker_compose.yaml
|-- setup_pi_stack.sh
|-- glance
|   |-- assets
|   `-- config
`-- README.md
```

Important generated files are ignored by Git:

- macOS metadata files
- Python cache files
- local path lists
- Uptime Kuma backups

## First Time Setup

### 1. Install Python Packages

On the computer where you run the desktop tool:

```bash
python3 -m pip install paramiko scp
```

Tkinter is also required. It is included with many Python installs. If the app does not open, install Tkinter for your system.

### 2. Make Sure The Pi Has SSH Enabled

The desktop app connects over SSH. You need:

- The Pi IP address
- The Pi username
- The Pi password
- A user account that can run `sudo`

### 3. Run The Desktop App

```bash
python3 deploy_tool.py
```

## Using The Desktop App

The app has several tabs.

### Connection

Use this tab to enter:

- Pi IP address
- Username
- Password
- Whether to save the password locally

Click `TEST CONNECTION` to confirm SSH works.

### Paths

Use this tab to tell the app where your local files are.

Set these paths:

- Hardware Script
- Docker Compose
- Glance Config Folder
- Glance Assets Folder
- Kuma Backup Folder
- Systemd Service File

Common values for this repo:

```text
Docker Compose: docker_compose.yaml
Glance Config Folder: glance/config
Glance Assets Folder: glance/assets
```

If you use the Steam widgets, create this file on the Pi before starting or restarting the stack:

```bash
cd /srv/docker/compose/core
nano .env
```

Add:

```text
STEAM_API_KEY=your-steam-api-key
STEAM_ID=your-steam-id
```

Then restart the stack:

```bash
docker compose up -d
```

You can also add:

- Website folders
- Discord bot folders

For a website, choose the local folder, the Node file, the host port, and the container port.

For a Discord bot, choose the local folder and the Node entry file.

Click `SAVE PATHS` when finished.

### Provision

Use this tab for a full setup on the Pi.

Provisioning does this:

- Updates apt packages
- Installs basic dependencies
- Installs Docker and Docker Compose
- Enables Docker
- Creates `/srv/docker` folders
- Uploads Docker Compose
- Uploads the hardware monitor script
- Uploads the systemd service file
- Uploads Glance config
- Uploads Glance assets
- Enables and restarts the hardware monitor service
- Adds a weekly reboot cron job
- Starts the Docker stack

Use this when setting up a fresh Pi or rebuilding the stack.

### Services

Use this tab for common Pi service tasks.

Available actions include:

- Start Docker stack
- Stop Docker stack
- Restart Docker stack
- Restart Glance
- Replace Docker Compose
- Restart hardware monitor
- View hardware monitor status
- View running Docker containers
- Import Glance config from the Pi
- Replace Glance config on the Pi
- Add Glance assets
- Backup Uptime Kuma data
- Restore Uptime Kuma data

### Website Control Panel

Use this tab after adding websites in the Paths tab.

For each website you can:

- Upload all files
- Upload only selected files or folders
- Add Docker Compose blocks
- Remove Docker Compose blocks
- Start the website service
- Stop the website service
- Restart the website service
- Check if it is running
- View logs
- Show generated Compose snippets

The uploader skips common local junk like:

- `.git`
- `.vs`
- `__pycache__`
- `node_modules`
- `uploads`
- `.DS_Store`
- `._*`

### Discord Bot Control

Use this tab after adding Discord bots in the Paths tab.

For each bot you can:

- Upload all files
- Upload only selected files or folders
- Deploy all entries
- Add Docker Compose blocks
- Remove Docker Compose blocks
- Start a bot service
- Stop a bot service
- Restart a bot service
- Check if it is running
- View logs
- Show generated Compose snippets

### Logs

Use this tab to see command output from SSH, Docker, uploads, and service actions.

You can also:

- Export the log
- Clear the log

## Using The Setup Script Directly

You can run the setup script on the Pi without the desktop app.

Copy `setup_pi_stack.sh` to the Pi, then run:

```bash
chmod +x setup_pi_stack.sh
./setup_pi_stack.sh
```

The script installs Docker, writes a basic Docker Compose file, creates folders, and starts the stack.

The desktop app is better for repeat deployments because it also uploads local config, assets, websites, bots, and backup data.

## Common Tasks

### Push Changes To The Pi

1. Open the desktop app.
2. Go to `Connection`.
3. Test the connection.
4. Go to `Services`.
5. Use `REPLACE DOCKER COMPOSE`, `REPLACE GLANCE CONFIG`, or `ADD GLANCE ASSETS`.
6. Restart the service if needed.

### Add A New Website

1. Go to `Paths`.
2. In `Website Paths`, click `+`.
3. Enter a website name.
4. Choose the local website folder.
5. Pick the Node entry file, usually `app.js` or `server.js`.
6. Set the host port and container port.
7. Save it.
8. Go to `Website Control Panel`.
9. Click `UPDATE FILES`.
10. Click `ADD COMPOSE`.
11. Click `START` or `RESTART`.

### Add A New Discord Bot

1. Go to `Paths`.
2. In `Discord Bot Paths`, click `+`.
3. Enter a bot name.
4. Choose the local bot folder.
5. Pick the Node entry file, usually `index.js`.
6. Save it.
7. Go to `Discord Bot Control`.
8. Click `DEPLOY ALL`.

### Backup Uptime Kuma

1. Go to `Paths`.
2. Set `Kuma Backup Folder`.
3. Go to `Services`.
4. Click `BACKUP KUMA DATA`.

### Restore Uptime Kuma

1. Go to `Paths`.
2. Set `Kuma Backup Folder` to the backup folder you want to restore.
3. Go to `Services`.
4. Click `RESTORE KUMA DATA`.

## Remote Pi Paths

The app uses these paths on the Pi:

```text
/srv/docker/compose/core
/srv/docker/data/kuma
/srv/docker/data/glance/config
/srv/docker/data/glance/assets
/srv/docker/data/websites
/srv/docker/data/discord-bots
/srv/samba/share/pi_housing_code
```

## GitHub Upload

After making changes locally:

```bash
git status
git add .
git commit -m "Update PiDeploy"
git push origin main
```

Check `git status` before committing so you know exactly what is going up.

## Notes

- Do not commit private API keys, passwords, `.env` files, or database backups.
- `deploy_tool_settings.json` may contain local paths and saved connection settings.
- `website_paths.json` and `discord_bot_paths.json` are local machine files and are ignored by Git.
- `kuma_backup/` is ignored because backups can contain private monitor data.
- If Docker commands fail right after setup, log out and back in on the Pi or run `newgrp docker`.
