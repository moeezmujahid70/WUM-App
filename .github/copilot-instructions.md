# Copilot Instructions for WUM

WUM is a PyQt5 desktop app for email warmup and campaign automation.

## Fast Start

- Setup: `python -m venv env && source env/bin/activate && pip install -r requirements.txt`
- Run app: `python var.py`
- Minimal test/check script: `python test.py`
- Build Windows executable: `pyinstaller --clean WUM.spec`

Use Python 3.8+ (README says 3.8; CI uses newer versions for build).

## Architecture at a Glance

- Entrypoint and global state: `var.py`
- Main app controller and UI behavior: `main.py`
- SMTP sending pipeline and AI-mode body generation: `smtp.py`
- IMAP reading and mailbox processing: `imap.py`
- Async reply workflow: `async_reply.py`
- Proxy support wrappers: `proxy_imaplib.py`, `proxy_smtplib.py`
- Server/orchestrator integration: `server_client.py`
- Utility helpers (templating, formatting, config updates): `utils.py`
- Thread-safe UI alerts/dialog fallbacks: `compat_ui.py`

## Module Ownership Map

- `var.py`
  - Loads config from `data/wum_config/config.json`
  - Loads mail settings from `data/gmonster_config/gmonster_config.json`
  - Loads sender sheets from `data/sheets/group_a.xlsx` and `data/sheets/group_b.xlsx`
  - Stores global runtime state (`cancel`, phase/cache state, AI settings)
  - Configures logging in `logs/wum.log`
  - Handles single-instance lock and cert bundle override for frozen builds

- `main.py`
  - Wires UI callbacks to actions
  - Starts and stops campaign threads (`smtp.main`)
  - Handles cached-run resume prompt and progress/status updates
  - Controls compose mode (`canned` vs `ai`)

- `smtp.py`
  - Primary campaign execution logic
  - Builds and sends outbound emails
  - Applies templates/prompts and AI mode behavior
  - Writes progress/report artifacts

- `imap.py`
  - Connects to IMAP and reads mailbox data
  - Extracts content and supports reply/spam workflows

- `async_reply.py`
  - Monitors inbox and queues auto replies in background threads

- `proxy_imaplib.py`, `proxy_smtplib.py`
  - Proxy-aware transport adapters for IMAP/SMTP

- `server_client.py`
  - Client for warming server endpoints and remote coordination

- `utils.py`
  - Email/body formatting helpers
  - Spintax and placeholder processing
  - Config update helper routines

- `dialog.py`
  - Progress/download dialogs and process-launch helpers

## UI Files and Edit Rules

Generated files are overwritten by PyQt tools. Do not hand-edit generated Python UI modules:

- `gui.py`
- `p_gui.py`
- `authentication.py`
- `sign_in.py`
- `sign_up.py`
- `logo_rc.py`

Edit source designer/resource files instead:

- `ui/gui.ui`
- `ui/progressbar.ui`
- `ui/authentication.ui`
- `ui/sign_in.ui`
- `ui/sign_up.ui`
- `ui/logo.qrc`

Then regenerate the Python outputs with `pyuic5`/`pyrcc5`.

## Runtime Data and Config Directories

- `data/wum_config/`
  - User-facing runtime config and cache (`config.json`, `cache.json`, text templates)

- `data/gmonster_config/`
  - Mail server config, blacklist/allowlist, cert bundle, scheduler artifacts

- `data/sheets/`
  - Sender source files (`group_a.xlsx`, `group_b.xlsx`, etc.)

- `data/`
  - Additional runtime outputs and mirrored config/data folders

- `logs/`
  - App logs (`wum.log`)

## Project Conventions

- Threads should respect `var.cancel` for shutdown.
- Keep cross-thread communication queue-based when possible.
- Prefer changing behavior in `main.py`, `smtp.py`, `imap.py`, `async_reply.py`, and `utils.py`.
- Avoid editing generated artifacts in `build/` and `dist/`.
- Keep path handling compatible with Windows and macOS.

## Common Pitfalls

- Config exists in multiple directories (`data/wum_config/`, `data/gmonster_config/`, and mirrored data folders). Verify which source a code path reads before changing defaults.
- Global mutable state in `var.py` can cause thread-order bugs.
- Editing generated UI Python files will be lost after regeneration.
- Frozen app cert behavior depends on `data/gmonster_config/cacert.pem` in `var.py`.

## Documentation Links

- Setup and run basics: `README.md`
- Packaging settings: `WUM.spec`
- Windows build CI: `.github/workflows/build-windows-exe.yml`
