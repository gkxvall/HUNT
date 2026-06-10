# HUNT

![HUNT logo](huntLogo.png)

HUNT is a privacy-first Python CLI assistant for internship applications. You give it a company website URL, a local CV file path, and a target company email address. It reads the website, reads your CV locally, uses a local Ollama model, drafts a tailored internship application email, previews it in the terminal, and only sends after explicit confirmation.

HUNT does not use the OpenAI API and does not require any cloud LLM API key.

## Features

- Local LLM generation through Ollama at `http://localhost:11434`
- Three-step drafting pipeline: company summary, candidate summary, email generation
- Optional applicant profile from `.env`
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

Beginner setup can stay tiny:

```bash
OLLAMA_MODEL=llama3.1:8b
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=your_gmail_app_password
```

The expanded profile variables are optional personalization fields. You do not need to fill them all.

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

Show the loaded non-secret configuration:

```bash
python main.py config
```

Check Ollama:

```bash
python main.py check-llm
```

Save the final email prompt and filtered config snapshot:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com --debug-prompt
```

This writes:

- `data/last_prompt.txt`
- `data/last_config_snapshot.json`

The debug files do not include `EMAIL_APP_PASSWORD` or the full sender email.

Save raw and parsed local model outputs:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com --debug-llm-output
```

This writes:

- `data/debug/company_raw.txt`
- `data/debug/company_parsed.json`
- `data/debug/candidate_raw.txt`
- `data/debug/candidate_parsed.json`
- `data/debug/email_raw.txt`
- `data/debug/email_parsed.json`

HUNT asks Ollama for JSON mode when possible, then repairs or falls back when the model returns markdown, text around JSON, Python-style dictionaries, or normal email text.

## Environment Variables

HUNT reads `.env` with `python-dotenv`.

HUNT reloads `.env` every time `load_config()` runs, using `override=True`, so edits are reflected in `python main.py config` and the next `apply` run.

All applicant fields are optional. Empty, missing, whitespace-only, and placeholder-like values such as `N/A`, `None`, `your_email@gmail.com`, `your_name`, `your username`, and `example.com` are ignored completely. Ignored values are not passed to the LLM, not shown in the preview, and not included in signatures.

Option variables have safe defaults. Boolean variables accept `true/false`, `yes/no`, `1/0`, and `on/off`.

To confirm `.env` changes are being applied:

```bash
python main.py config
```

Check the `.env loaded` path, style values, profile fields passed to the LLM, signature fields, and internship fields. For deeper debugging, run `apply` with `--debug-prompt` and inspect `data/last_prompt.txt`.

### Local LLM

- `OLLAMA_MODEL`: local Ollama model. Default: `llama3.1:8b`

### Email Sending

- `EMAIL_ADDRESS`: Gmail address used for sending only
- `EMAIL_APP_PASSWORD`: Gmail app password used for sending only

HUNT never shows `EMAIL_APP_PASSWORD`. If the sending address is shown in the preview, it is masked.

### Applicant Identity

- `APPLICANT_FULL_NAME`
- `APPLICANT_PREFERRED_NAME`
- `APPLICANT_NATIONALITY`
- `APPLICANT_CURRENT_LOCATION`
- `APPLICANT_TIMEZONE`
- `APPLICANT_SHORT_BIO`

### Applicant Contact

- `APPLICANT_PERSONAL_EMAIL`
- `APPLICANT_PHONE`
- `APPLICANT_WHATSAPP`
- `APPLICANT_TELEGRAM`
- `APPLICANT_DISCORD`

Phone is used only when `EMAIL_INCLUDE_PHONE=true`.

### Applicant Links

- `APPLICANT_PORTFOLIO_URL`
- `APPLICANT_BLOG_URL`
- `APPLICANT_GITHUB_URL`
- `APPLICANT_LINKEDIN_URL`
- `APPLICANT_KAGGLE_URL`
- `APPLICANT_GOOGLE_SCHOLAR_URL`
- `APPLICANT_ORCID_URL`
- `APPLICANT_MEDIUM_URL`
- `APPLICANT_DEVTO_URL`
- `APPLICANT_YOUTUBE_URL`
- `APPLICANT_PERSONAL_WEBSITE_URL`

Links are used only when `EMAIL_INCLUDE_LINKS=true`.

### Education

- `APPLICANT_UNIVERSITY`
- `APPLICANT_FACULTY`
- `APPLICANT_DEPARTMENT`
- `APPLICANT_DEGREE`
- `APPLICANT_YEAR_LEVEL`
- `APPLICANT_EXPECTED_GRADUATION`
- `APPLICANT_GPA`
- `APPLICANT_GPA_SCALE`
- `APPLICANT_RELEVANT_COURSEWORK`: comma-separated
- `APPLICANT_ACADEMIC_ADVISOR`
- `APPLICANT_UNIVERSITY_COUNTRY`
- `APPLICANT_UNIVERSITY_CITY`

GPA is used only when `EMAIL_INCLUDE_GPA=true`.

### Skills And Interests

- `APPLICANT_MAIN_INTERESTS`: comma-separated
- `APPLICANT_TECHNICAL_SKILLS`: comma-separated
- `APPLICANT_PROGRAMMING_LANGUAGES`: comma-separated
- `APPLICANT_FRAMEWORKS`: comma-separated
- `APPLICANT_TOOLS`: comma-separated
- `APPLICANT_RESEARCH_INTERESTS`: comma-separated
- `APPLICANT_SOFT_SKILLS`: comma-separated
- `APPLICANT_LANGUAGES`: comma-separated

Languages are used only when `EMAIL_INCLUDE_LANGUAGES=true`.

### Projects And Experience Highlights

Optional extra highlights beyond the CV:

- `APPLICANT_TOP_PROJECT_1_NAME`
- `APPLICANT_TOP_PROJECT_1_URL`
- `APPLICANT_TOP_PROJECT_1_DESCRIPTION`
- `APPLICANT_TOP_PROJECT_2_NAME`
- `APPLICANT_TOP_PROJECT_2_URL`
- `APPLICANT_TOP_PROJECT_2_DESCRIPTION`
- `APPLICANT_TOP_PROJECT_3_NAME`
- `APPLICANT_TOP_PROJECT_3_URL`
- `APPLICANT_TOP_PROJECT_3_DESCRIPTION`
- `APPLICANT_TOP_EXPERIENCE_1_TITLE`
- `APPLICANT_TOP_EXPERIENCE_1_ORGANIZATION`
- `APPLICANT_TOP_EXPERIENCE_1_DESCRIPTION`
- `APPLICANT_TOP_EXPERIENCE_2_TITLE`
- `APPLICANT_TOP_EXPERIENCE_2_ORGANIZATION`
- `APPLICANT_TOP_EXPERIENCE_2_DESCRIPTION`

HUNT asks the local model to use these together with the CV, avoid duplicate mentions, and prefer the richer project description if a project appears in both places.

### Internship Preferences

- `INTERNSHIP_MODE`: `remote`, `on-site`, `hybrid`, `flexible`. Default: `remote`
- `INTERNSHIP_TYPE`: `internship`, `summer internship`, `mandatory internship`, `voluntary internship`, `research internship`, `part-time internship`. Default: `internship`
- `INTERNSHIP_FIELD_PREFERENCES`: comma-separated
- `INTERNSHIP_TARGET_ROLES`: comma-separated
- `INTERNSHIP_AVAILABILITY_START`
- `INTERNSHIP_AVAILABILITY_END`
- `INTERNSHIP_DURATION`
- `INTERNSHIP_HOURS_PER_WEEK`
- `INTERNSHIP_RELOCATION_OPEN`: boolean. Default: `false`
- `INTERNSHIP_WORK_AUTHORIZATION`
- `INTERNSHIP_VISA_STATUS`
- `INTERNSHIP_UNIVERSITY_REQUIREMENT`: boolean. Default: `true`
- `INTERNSHIP_INSURANCE_COVERED_BY_UNIVERSITY`: boolean. Default: `true`
- `INTERNSHIP_REMOTE_REASON`
- `INTERNSHIP_NOTE`

Availability is used only when `EMAIL_INCLUDE_AVAILABILITY=true`. Remote reason is used only when `EMAIL_INCLUDE_REMOTE_REASON=true`.

### Email Style

- `EMAIL_LANGUAGE`: output language, for example `English`, `Turkish`, `French`, or `Arabic`
- `EMAIL_ACADEMIC_LEVEL`: `A`, `B`, or `C`. Default: `B`
- `EMAIL_TONE`: `professional`, `warm`, `confident`, `humble`, `startup`, `research-focused`, `formal`, or `friendly`
- `EMAIL_LENGTH`: `short`, `medium`, or `long`
- `EMAIL_MAX_WORDS`: hard body limit from `80` to `700`. Default: `350`
- `EMAIL_FORMAT`: `compact` or `full`
- `EMAIL_GREETING_STYLE`: `team`, `hiring-team`, `recruiter`, or `formal`
- `EMAIL_SIGNATURE_STYLE`: `minimal`, `compact`, or `detailed`
- `EMAIL_INCLUDE_SUBJECT_KEYWORDS`: boolean
- `EMAIL_INCLUDE_CV_ATTACHMENT_NOTE`: boolean
- `EMAIL_INCLUDE_UNIVERSITY_REQUIREMENT`: boolean
- `EMAIL_INCLUDE_INSURANCE_NOTE`: boolean
- `EMAIL_INCLUDE_LINKS`: boolean
- `EMAIL_INCLUDE_PHONE`: boolean
- `EMAIL_INCLUDE_LOCATION`: boolean
- `EMAIL_INCLUDE_GPA`: boolean
- `EMAIL_INCLUDE_LANGUAGES`: boolean
- `EMAIL_INCLUDE_AVAILABILITY`: boolean
- `EMAIL_INCLUDE_REMOTE_REASON`: boolean

Academic levels:

- `A`: casual/simple student tone; direct, friendly, simple words, less formal, suitable for startups
- `B`: balanced professional tone; professional but natural, not too academic, not too casual
- `C`: highly academic/formal tone; more structured, suitable for research labs, universities, academic internships, and R&D departments

Length guide:

- `short`: guides the model toward 150-220 words
- `medium`: guides the model toward 250-400 words
- `long`: guides the model toward 400-650 words

`EMAIL_MAX_WORDS` remains the hard instruction even when length is set.

Signature styles:

- `minimal`: sign-off and name if available
- `compact`: name plus selected links on one concise line
- `detailed`: name, email, phone/location if enabled, and selected links on separate lines

Example:

```bash
APPLICANT_FULL_NAME=Vall
APPLICANT_CURRENT_LOCATION=Istanbul, Turkey
APPLICANT_UNIVERSITY=Example University
APPLICANT_DEPARTMENT=Computer Engineering
APPLICANT_GITHUB_URL=https://github.com/gkxvall
APPLICANT_LINKEDIN_URL=
APPLICANT_TECHNICAL_SKILLS=Python, Machine Learning, FastAPI
APPLICANT_GPA=3.7
EMAIL_LANGUAGE=English
EMAIL_ACADEMIC_LEVEL=B
EMAIL_TONE=warm
EMAIL_INCLUDE_LINKS=true
EMAIL_INCLUDE_LOCATION=false
EMAIL_INCLUDE_GPA=false
EMAIL_SIGNATURE_STYLE=compact
```

With this setup, HUNT can use the name, university, department, GitHub URL, and technical skills. It ignores the empty LinkedIn value, does not mention location, and does not mention GPA because those include flags are disabled.

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
