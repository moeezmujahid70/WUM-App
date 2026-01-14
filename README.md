# WUM

## Requirements

- Python 3.8

## Setup

1. Clone repository

```bash
git clone https://github.com/lildoktor/WUM.git
cd Gmonster
```

2. Create virtual environment (optional)

```bash
python -m venv env
```

3. Activate environment (if you have created virtual environment)

```bash
# CMD/PowerShell:
env\Scripts\activate

# zsh/bash in windows:
source env/Scripts/activate 

# Linux/MacOs:
source env/bin/activate
```

4. Install requirements

```bash
pip install -r requirements.txt
```

5. Run application

```bash
python var.py
```

## AI Mode

- Set the `OPENAI_API_KEY` environment variable (or add `openai_api_key` inside `wum_config/config.json`).
- Optional overrides: `OPENAI_MODEL`, `OPENAI_BASE_URL`, and `OPENAI_TIMEOUT`.
- Customize the outbound AI prompt/template via `database/PROMPT1.txt` and `database/EMAIL1.txt`.
- Customize the reply AI prompt/template via `database/PROMPT2.txt` and `database/EMAIL2.txt`.
- Enable **AI Mode** in the Compose screen to have GPT generate personalized send emails *and* follow-up replies (fallbacks to canned content when disabled or on errors).
