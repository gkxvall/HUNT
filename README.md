# HUNT

HUNT is a privacy-first Python CLI assistant for internship applications. You give it a company website URL, a local CV file path, and a target company email address. It reads the website, reads your CV locally, uses a local Ollama model, drafts a tailored internship application email, previews it in the terminal, and only sends after explicit confirmation.

HUNT does not use the OpenAI API and does not require any cloud LLM API key.

## Features

- Local LLM generation through Ollama at `http://localhost:11434`
- Three-step drafting pipeline: company summary, candidate summary, email generation
- PDF, DOCX, and TXT CV parsing
- Website extraction with `trafilatura` and BeautifulSoup fallback
- Rich terminal previews
- Gmail SMTP sending with confirmation
- SQLite application tracking
- Privacy-first flow: your CV stays on your machine

## Installation

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the environment example:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
OLLAMA_MODEL=llama3.1:8b
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=your_gmail_app_password
```

## Ollama Setup

Install Ollama from [ollama.com](https://ollama.com), then start the local server:

```bash
ollama serve
```

Pull the default model:

```bash
ollama pull llama3.1:8b
```

Check HUNT can see it:

```bash
python main.py check-llm
```

## Gmail App Password Setup

Gmail SMTP requires an app password, not your normal Gmail password.

1. Enable 2-Step Verification on your Google account.
2. Create an app password for Mail.
3. Put your Gmail address and app password in `.env`.

HUNT uses Gmail SMTP SSL on port 465.

## Usage

Generate a preview only:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com
```

Generate and ask before sending:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com --send
```

Show tracked applications:

```bash
python main.py history
```

Check Ollama:

```bash
python main.py check-llm
```

## Safety Behavior

- HUNT never sends automatically.
- Without `--send`, it only previews the generated email.
- With `--send`, it still asks for confirmation.
- If Ollama is not running, HUNT tells you to run `ollama serve`.
- If the configured model is missing, HUNT suggests `ollama pull llama3.1:8b`.
- If SMTP credentials are missing, sending stops with a clear error.

## Privacy Note

Your CV is read from your local filesystem and sent only to your local Ollama server. No cloud LLM API is used. If you choose to send an email, the email and attached CV are sent through Gmail SMTP to the recipient you provide.

## Roadmap

- More email providers
- Configurable attachment behavior
- Multiple draft styles
- Company name detection
- Better duplicate tracking
- Optional cover letter generation
