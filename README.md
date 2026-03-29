# WUM

WUM is a PyQt5 desktop app for email warmup and campaign automation.

## Features

- Multi-phase warmup sending with configurable delays and per-phase schedules.
- SMTP sending pipeline with optional AI-generated outreach and reply content.
- IMAP inbox processing and async auto-reply workflow.
- Centralized target mode support through server endpoints.
- Proxy-aware SMTP and IMAP connections.
- Windows executable packaging support via PyInstaller.

## Requirements

- Python 3.8+
- Access to SMTP/IMAP credentials for sender accounts
- Optional: OpenAI API key for AI Mode

## Quick Start

1. Clone repository

```bash
git clone https://github.com/lildoktor/WUM.git
cd WUM
```

2. Create a virtual environment

```bash
python -m venv env
```

3. Activate environment

```bash
# CMD/PowerShell
env\Scripts\activate

# zsh/bash on Windows
source env/Scripts/activate

# Linux/macOS
source env/bin/activate
```

4. Install dependencies

```bash
pip install -r requirements.txt
```

5. Run the app

```bash
python var.py
```

## Project Structure

- `var.py`: entrypoint, global state, config/bootstrap loading
- `main.py`: UI event wiring and main workflow controls
- `smtp.py`: outbound send logic, AI body generation, phase execution
- `imap.py`: inbox reading and response processing
- `async_reply.py`: background async reply orchestration
- `utils.py`: formatting, spintax, helper routines
- `server_client.py`: centralized mode and remote service integration
- `proxy_imaplib.py`, `proxy_smtplib.py`: proxy transport adapters

## Data and Config Directories

WUM now reads runtime files from `data/*` paths.

- `data/wum_config/`
  - user runtime config and templates
  - expected files: `config.json`, `cache.json`, `subject.txt`, `body.txt`,
    `PROMPT1.txt`, `PROMPT2.txt`, `EMAIL1.txt`, `EMAIL2.txt`

- `data/gmonster_config/`
  - mail server config and SSL cert bundle
  - expected files: `gmonster_config.json`, `cacert.pem`, and scheduler artifacts

- `data/sheets/`
  - sender sheets used by `load_db()`
  - expected files: `group_a.xlsx`, `group_b.xlsx`

- `data/email/results/`
  - report outputs such as `report.csv` and `followup_report.csv`

## AI Mode

### Configure API Access

- Set `OPENAI_API_KEY`, or add `openai_api_key` in `data/wum_config/config.json`.
- Optional overrides:
  - `OPENAI_MODEL`
  - `OPENAI_BASE_URL`
  - `OPENAI_TIMEOUT`

### Customize Prompts and Templates

- Outbound prompt/template:
  - `data/wum_config/PROMPT1.txt`
  - `data/wum_config/EMAIL1.txt`

- Reply prompt/template:
  - `data/wum_config/PROMPT2.txt`
  - `data/wum_config/EMAIL2.txt`

### Behavior

- Enable AI Mode in Compose UI to generate personalized send emails and follow-up replies.
- If AI generation fails, WUM falls back to canned subject/body flow.

## Running Checks

- Minimal script:

```bash
python test.py
```

- Main app launch:

```bash
python var.py
```

## Build Windows Executable

Use the existing spec file:

```bash
pyinstaller --clean WUM.spec
```

Build output is generated under `dist/`.

## Troubleshooting

- Missing config errors:
  - verify required files exist under `data/wum_config/`, `data/gmonster_config/`, and `data/sheets/`

- SSL/certificate issues in packaged mode:
  - verify `data/gmonster_config/cacert.pem` is present

- Sender load issues:
  - verify Excel sheets exist and include required columns (`EMAIL`, `PROXY:PORT`, etc.)

- UI or thread-stop issues:
  - ensure long-running tasks respect cancellation through shared state

## Notes

- Do not hand-edit generated UI Python files (`gui.py`, `p_gui.py`, etc.).
- Edit `.ui` sources in `ui/` and regenerate when changing forms/resources.
