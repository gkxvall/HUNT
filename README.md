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

# Optional applicant fields. Blank values are omitted completely.
APPLICANT_FULL_NAME=
APPLICANT_PHONE=
APPLICANT_LOCATION=
APPLICANT_PERSONAL_EMAIL=
APPLICANT_PORTFOLIO_URL=
APPLICANT_BLOG_URL=
APPLICANT_GITHUB_URL=
APPLICANT_LINKEDIN_URL=

EMAIL_LANGUAGE=English
EMAIL_ACADEMIC_LEVEL=B
EMAIL_TONE=professional
EMAIL_MAX_WORDS=180
EMAIL_INCLUDE_LINKS=true
EMAIL_INCLUDE_PHONE=false
EMAIL_INCLUDE_LOCATION=false
EMAIL_SIGNATURE_STYLE=compact
```

## Configuration

HUNT reads configuration from `.env` with `python-dotenv`. All applicant profile fields are optional. If a value is empty, missing, or only whitespace, HUNT omits it completely from the prompt, signature, preview, and logs. It will never ask the model to use placeholders such as portfolio links, phone numbers, or names that you did not provide.

Core settings:

- `OLLAMA_MODEL`: local Ollama model, default `llama3.1:8b`
- `EMAIL_ADDRESS`: Gmail address used only for sending
- `EMAIL_APP_PASSWORD`: Gmail app password used only for sending

Applicant profile fields:

- `APPLICANT_FULL_NAME`: name for the signature and optional introduction
- `APPLICANT_PHONE`: included only when `EMAIL_INCLUDE_PHONE=true`
- `APPLICANT_LOCATION`: included only when `EMAIL_INCLUDE_LOCATION=true`
- `APPLICANT_PERSONAL_EMAIL`: email for detailed signatures
- `APPLICANT_PORTFOLIO_URL`: included only when links are enabled
- `APPLICANT_BLOG_URL`: included only when links are enabled
- `APPLICANT_GITHUB_URL`: included only when links are enabled
- `APPLICANT_LINKEDIN_URL`: included only when links are enabled

Email style fields:

- `EMAIL_LANGUAGE`: output language, for example `English`, `Turkish`, `French`, or `Arabic`
- `EMAIL_ACADEMIC_LEVEL`: `A`, `B`, or `C`
- `EMAIL_TONE`: extra tone hint such as `professional`, `warm`, `confident`, `humble`, `startup`, or `research-focused`
- `EMAIL_MAX_WORDS`: maximum body word count
- `EMAIL_INCLUDE_LINKS`: `true` or `false`
- `EMAIL_INCLUDE_PHONE`: `true` or `false`
- `EMAIL_INCLUDE_LOCATION`: `true` or `false`
- `EMAIL_SIGNATURE_STYLE`: `compact`, `detailed`, or `minimal`

Academic levels:

- `A`: casual/simple student tone; direct, friendly, simple words, less formal, suitable for startups
- `B`: balanced professional tone; professional but natural, not too academic, not too casual
- `C`: highly academic/formal tone; more structured, suitable for research labs, universities, academic internships, and R&D departments

Signature styles:

- `compact`: short signature with name and selected links
- `detailed`: name, email, phone/location if enabled, and selected links on separate lines
- `minimal`: name only

Example profile:

```bash
APPLICANT_FULL_NAME=Vall
APPLICANT_GITHUB_URL=https://github.com/gkxvall
APPLICANT_LINKEDIN_URL=
APPLICANT_PHONE=
EMAIL_LANGUAGE=English
EMAIL_ACADEMIC_LEVEL=B
EMAIL_TONE=warm
EMAIL_INCLUDE_LINKS=true
EMAIL_INCLUDE_PHONE=true
EMAIL_SIGNATURE_STYLE=compact
```

With that profile, HUNT sends only the non-empty, enabled fields to the local model: the name and GitHub URL. It does not send or mention empty LinkedIn or phone values.

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
