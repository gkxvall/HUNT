# HUNT

![HUNT logo](./assets/huntLogo.png)

Privacy-first local LLM CLI for drafting, previewing, tracking, and optionally sending tailored internship application emails.

## What Is HUNT?

HUNT helps students create personalized internship application emails from local inputs.

You provide:

- a company website URL
- a local CV file path
- a target company email address

HUNT then:

- reads the company website
- reads your CV locally
- uses a local Ollama model through `http://localhost:11434`
- generates a tailored internship application email
- previews the email in the terminal
- optionally sends it through Gmail SMTP after confirmation
- tracks the application in SQLite

HUNT does not use the OpenAI API and does not require any cloud LLM API key.

![HUNT Demo](assets/demo.gif)

## Why HUNT?

Applying to internships often means repeating the same work: reading the company, adapting your background, writing a concise email, and remembering where you applied. HUNT helps with that flow while keeping the important parts under your control.

Benefits:

- Saves time when applying to internships.
- Keeps your CV local by default.
- Produces company-specific emails instead of generic copy-paste messages.
- Supports optional applicant profile details from `.env`.
- Helps track application history.
- Works locally for CV parsing and LLM generation.
- Sends email only when you explicitly enable sending and confirm it.

## Key Features

- [x] Local Ollama model support
- [x] No OpenAI API key
- [x] No cloud LLM API key
- [x] Website text extraction with fallback parsing
- [x] PDF, DOCX, and TXT CV parsing
- [x] Optional applicant profile from `.env`
- [x] Configurable language, tone, academic level, email length, and signature style
- [x] JSON repair and sanitization for messy local model outputs
- [x] Rich CLI preview
- [x] Preview-first single-application workflow
- [x] Optional Gmail SMTP sending with confirmation
- [x] SQLite application tracking
- [x] Debug prompt and raw LLM output tools
- [x] Safe CSV batch mode
- [x] Sequential sending safeguards for batch mode

## How HUNT Works

```text
Company website + CV + applicant config
        |
        v
Website extraction
        |
        v
CV parsing
        |
        v
Local Ollama model
        |
        v
Email generation
        |
        v
Preview
        |
        v
Draft / Send / Track
```

Current generation uses the structured full pipeline:

1. Summarize the company.
2. Summarize the candidate from the CV.
3. Merge optional `.env` applicant profile details.
4. Generate the final email.
5. Parse, sanitize, validate, and preview the output.

This full pipeline is slower than a single prompt, but it gives HUNT more structure and better debugging information. A future fast mode may use one LLM call for low-resource machines.

## Requirements

- Python 3.11+
- Ollama
- A local Ollama model
- Gmail account only if you want SMTP sending
- macOS, Linux, or Windows PowerShell

HUNT can draft emails without Gmail credentials. SMTP credentials are needed only when you use `--send`.

## Quick Start

macOS or Linux:

```bash
git clone https://github.com/gkxvall/HUNT.git
cd HUNT
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell:

```powershell
git clone https://github.com/gkxvall/HUNT.git
cd HUNT
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Important:

- `.env.example` is only a public template.
- HUNT reads `.env`, not `.env.example`.
- `.env` is your private local config.
- Never commit `.env`.

## Install And Start Ollama

Start Ollama:

```bash
ollama serve
```

In another terminal, pull the recommended low-resource model:

```bash
ollama pull qwen2.5:3b-instruct
```

Set it in `.env`:

```env
OLLAMA_MODEL=qwen2.5:3b-instruct
```

Model recommendations:

| Use case              | Model                 | Notes                                              |
| --------------------- | --------------------- | -------------------------------------------------- |
| MacBook Air / fastest | `qwen2.5:3b-instruct` | Recommended default for low-resource machines.     |
| Balanced quality      | `qwen2.5:7b-instruct` | Better output, slower.                             |
| Very lightweight      | `llama3.2:3b`         | Good fallback.                                     |
| Higher quality        | `mistral:7b`          | Slower, better for stronger machines.              |
| Avoid for strict JSON | `deepseek-r1`         | Reasoning models may output extra reasoning/noise. |

Check Ollama from HUNT:

```bash
python main.py check-llm
```

## Configure `.env`

Create your private config:

```bash
cp .env.example .env
```

Then edit `.env`.

Minimal example:

```env
OLLAMA_MODEL=qwen2.5:3b-instruct

EMAIL_ADDRESS=
EMAIL_APP_PASSWORD=

APPLICANT_FULL_NAME=
APPLICANT_UNIVERSITY=
APPLICANT_DEPARTMENT=
APPLICANT_GITHUB_URL=

EMAIL_LANGUAGE=English
EMAIL_ACADEMIC_LEVEL=B
EMAIL_TONE=professional
EMAIL_FORMAT=full
EMAIL_MAX_WORDS=350
```

Rules:

- All applicant fields are optional.
- Empty values are ignored completely.
- Empty values are not passed to the LLM.
- Empty values are not shown in the preview.
- HUNT does not output placeholders such as `None`, `N/A`, `[your name]`, or `[portfolio]`.
- Boolean values accept `true/false`, `yes/no`, `1/0`, and `on/off`.
- Comma-separated fields are supported where useful.
- Allowed options are shown in `.env.example`.
- If `.env` changes are not applying, run `python main.py config`.

## Environment Variables Reference

### Local LLM

| Variable                    |               Default | Options                    | Status      | Description                                                              |
| --------------------------- | --------------------: | -------------------------- | ----------- | ------------------------------------------------------------------------ |
| `OLLAMA_MODEL`              | `qwen2.5:3b-instruct` | Any installed Ollama model | Implemented | Local model used for generation.                                         |
| `OLLAMA_TIMEOUT_SECONDS`    |               Planned | Positive integer           | Planned     | Future request timeout override. Current code uses its built-in timeout. |
| `OLLAMA_NUM_CTX`            |               Planned | Positive integer           | Planned     | Future context-window override. Current Ollama calls use `8192`.         |
| `OLLAMA_MAX_WEBSITE_CHARS`  |               Planned | Positive integer           | Planned     | Future website text limit override.                                      |
| `OLLAMA_MAX_CV_CHARS`       |               Planned | Positive integer           | Planned     | Future CV text limit override.                                           |
| `OLLAMA_USE_FAST_MODE`      |               Planned | `true`, `false`            | Planned     | Future one-call generation mode.                                         |
| `OLLAMA_SKIP_SUMMARIZATION` |               Planned | `true`, `false`            | Planned     | Future shortcut to skip summary calls.                                   |

### Email Sending

| Variable                | Default | Options              | Status      | Description                                                                                       |
| ----------------------- | ------: | -------------------- | ----------- | ------------------------------------------------------------------------------------------------- |
| `EMAIL_ADDRESS`         |   empty | Gmail address        | Implemented | Sender address for SMTP sending.                                                                  |
| `EMAIL_APP_PASSWORD`    |   empty | Gmail app password   | Implemented | App password for Gmail SMTP. This is not your normal Gmail password.                              |
| `EMAIL_SEND_MODE`       | Planned | `smtp`, `draft-only` | Planned     | Future explicit send mode. Today, omit `--send` for preview behavior or use batch `--draft-only`. |
| `EMAIL_ATTACH_CV`       | Planned | `true`, `false`      | Planned     | Future attachment toggle. Today, HUNT attaches the CV when sending.                               |
| `EMAIL_ATTACHMENT_NAME` | Planned | text                 | Planned     | Future custom attachment filename.                                                                |

Gmail app password notes:

- A Gmail app password is not your normal Gmail password.
- It is generated inside your Google account security settings.
- It usually requires 2-Step Verification.
- It may be unavailable for school/work managed accounts.
- It may be unavailable for Advanced Protection or security-key-only setups.
- If you cannot create one, use preview mode or batch draft-only mode.

### Applicant Identity

| Variable                     | Default | Description                                                |
| ---------------------------- | ------: | ---------------------------------------------------------- |
| `APPLICANT_FULL_NAME`        |   empty | Name used in the introduction and signature when provided. |
| `APPLICANT_PREFERRED_NAME`   |   empty | Preferred name if different from full name.                |
| `APPLICANT_NATIONALITY`      |   empty | Optional nationality.                                      |
| `APPLICANT_CURRENT_LOCATION` |   empty | City/country. Used only when location is enabled.          |
| `APPLICANT_TIMEZONE`         |   empty | Optional timezone.                                         |
| `APPLICANT_SHORT_BIO`        |   empty | Short factual bio.                                         |

### Applicant Contact

| Variable                   | Default | Description                                  |
| -------------------------- | ------: | -------------------------------------------- |
| `APPLICANT_PERSONAL_EMAIL` |   empty | Email for detailed signatures when provided. |
| `APPLICANT_PHONE`          |   empty | Used only when `EMAIL_INCLUDE_PHONE=true`.   |
| `APPLICANT_WHATSAPP`       |   empty | Optional contact detail.                     |
| `APPLICANT_TELEGRAM`       |   empty | Optional contact detail.                     |
| `APPLICANT_DISCORD`        |   empty | Optional contact detail.                     |

Phone and location are never included unless both conditions are true:

1. The value exists.
2. The matching include option is enabled.

### Applicant Links

Links are used only when `EMAIL_INCLUDE_LINKS=true`.

| Variable                         | Default | Description           |
| -------------------------------- | ------: | --------------------- |
| `APPLICANT_PORTFOLIO_URL`        |   empty | Portfolio URL.        |
| `APPLICANT_BLOG_URL`             |   empty | Blog URL.             |
| `APPLICANT_GITHUB_URL`           |   empty | GitHub URL.           |
| `APPLICANT_LINKEDIN_URL`         |   empty | LinkedIn URL.         |
| `APPLICANT_KAGGLE_URL`           |   empty | Kaggle URL.           |
| `APPLICANT_GOOGLE_SCHOLAR_URL`   |   empty | Google Scholar URL.   |
| `APPLICANT_ORCID_URL`            |   empty | ORCID URL.            |
| `APPLICANT_MEDIUM_URL`           |   empty | Medium URL.           |
| `APPLICANT_DEVTO_URL`            |   empty | DEV.to URL.           |
| `APPLICANT_YOUTUBE_URL`          |   empty | YouTube URL.          |
| `APPLICANT_PERSONAL_WEBSITE_URL` |   empty | Personal website URL. |

### Education

GPA is used only when `EMAIL_INCLUDE_GPA=true`.

| Variable                        | Default | Description                    |
| ------------------------------- | ------: | ------------------------------ |
| `APPLICANT_UNIVERSITY`          |   empty | University name.               |
| `APPLICANT_FACULTY`             |   empty | Faculty or school.             |
| `APPLICANT_DEPARTMENT`          |   empty | Department or major.           |
| `APPLICANT_DEGREE`              |   empty | Degree type.                   |
| `APPLICANT_YEAR_LEVEL`          |   empty | Current year level.            |
| `APPLICANT_EXPECTED_GRADUATION` |   empty | Expected graduation date/year. |
| `APPLICANT_GPA`                 |   empty | GPA value.                     |
| `APPLICANT_GPA_SCALE`           |   empty | GPA scale, for example `4.0`.  |
| `APPLICANT_RELEVANT_COURSEWORK` |   empty | Comma-separated coursework.    |
| `APPLICANT_ACADEMIC_ADVISOR`    |   empty | Optional advisor.              |
| `APPLICANT_UNIVERSITY_COUNTRY`  |   empty | University country.            |
| `APPLICANT_UNIVERSITY_CITY`     |   empty | University city.               |

### Skills And Interests

These fields support comma-separated values.

| Variable                          | Default | Description                                                              |
| --------------------------------- | ------: | ------------------------------------------------------------------------ |
| `APPLICANT_MAIN_INTERESTS`        |   empty | Main career or technical interests.                                      |
| `APPLICANT_TECHNICAL_SKILLS`      |   empty | Technical skills.                                                        |
| `APPLICANT_PROGRAMMING_LANGUAGES` |   empty | Programming languages.                                                   |
| `APPLICANT_FRAMEWORKS`            |   empty | Frameworks.                                                              |
| `APPLICANT_TOOLS`                 |   empty | Tools.                                                                   |
| `APPLICANT_RESEARCH_INTERESTS`    |   empty | Research interests.                                                      |
| `APPLICANT_SOFT_SKILLS`           |   empty | Soft skills.                                                             |
| `APPLICANT_LANGUAGES`             |   empty | Spoken/written languages. Used only when `EMAIL_INCLUDE_LANGUAGES=true`. |

### Projects And Experience Highlights

These are optional extra highlights beyond the CV. The CV remains the main source.

| Variable                                  | Default | Description             |
| ----------------------------------------- | ------: | ----------------------- |
| `APPLICANT_TOP_PROJECT_1_NAME`            |   empty | Project name.           |
| `APPLICANT_TOP_PROJECT_1_URL`             |   empty | Project URL.            |
| `APPLICANT_TOP_PROJECT_1_DESCRIPTION`     |   empty | Project description.    |
| `APPLICANT_TOP_PROJECT_2_NAME`            |   empty | Project name.           |
| `APPLICANT_TOP_PROJECT_2_URL`             |   empty | Project URL.            |
| `APPLICANT_TOP_PROJECT_2_DESCRIPTION`     |   empty | Project description.    |
| `APPLICANT_TOP_PROJECT_3_NAME`            |   empty | Project name.           |
| `APPLICANT_TOP_PROJECT_3_URL`             |   empty | Project URL.            |
| `APPLICANT_TOP_PROJECT_3_DESCRIPTION`     |   empty | Project description.    |
| `APPLICANT_TOP_EXPERIENCE_1_TITLE`        |   empty | Experience title.       |
| `APPLICANT_TOP_EXPERIENCE_1_ORGANIZATION` |   empty | Organization.           |
| `APPLICANT_TOP_EXPERIENCE_1_DESCRIPTION`  |   empty | Experience description. |
| `APPLICANT_TOP_EXPERIENCE_2_TITLE`        |   empty | Experience title.       |
| `APPLICANT_TOP_EXPERIENCE_2_ORGANIZATION` |   empty | Organization.           |
| `APPLICANT_TOP_EXPERIENCE_2_DESCRIPTION`  |   empty | Experience description. |

### Internship Preferences

| Variable                                     |      Default | Options                                                                                                                          | Description                                         |
| -------------------------------------------- | -----------: | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `INTERNSHIP_MODE`                            |     `remote` | `remote`, `on-site`, `hybrid`, `flexible`                                                                                        | Preferred internship mode.                          |
| `INTERNSHIP_TYPE`                            | `internship` | `internship`, `summer internship`, `mandatory internship`, `voluntary internship`, `research internship`, `part-time internship` | Type of internship.                                 |
| `INTERNSHIP_FIELD_PREFERENCES`               |        empty | comma-separated                                                                                                                  | Preferred fields.                                   |
| `INTERNSHIP_TARGET_ROLES`                    |        empty | comma-separated                                                                                                                  | Target roles.                                       |
| `INTERNSHIP_AVAILABILITY_START`              |        empty | date/text                                                                                                                        | Start availability.                                 |
| `INTERNSHIP_AVAILABILITY_END`                |        empty | date/text                                                                                                                        | End availability.                                   |
| `INTERNSHIP_DURATION`                        |        empty | text                                                                                                                             | Desired duration.                                   |
| `INTERNSHIP_HOURS_PER_WEEK`                  |        empty | text                                                                                                                             | Weekly hours.                                       |
| `INTERNSHIP_RELOCATION_OPEN`                 |      `false` | `true`, `false`                                                                                                                  | Whether relocation is possible.                     |
| `INTERNSHIP_WORK_AUTHORIZATION`              |        empty | text                                                                                                                             | Work authorization note.                            |
| `INTERNSHIP_VISA_STATUS`                     |        empty | text                                                                                                                             | Visa status note.                                   |
| `INTERNSHIP_UNIVERSITY_REQUIREMENT`          |       `true` | `true`, `false`                                                                                                                  | Whether the internship is a university requirement. |
| `INTERNSHIP_INSURANCE_COVERED_BY_UNIVERSITY` |       `true` | `true`, `false`                                                                                                                  | Whether insurance is covered by the university.     |
| `INTERNSHIP_REMOTE_REASON`                   |        empty | text                                                                                                                             | Remote-work reason.                                 |
| `INTERNSHIP_NOTE`                            |        empty | text                                                                                                                             | Extra preference note.                              |

Availability fields are included only when `EMAIL_INCLUDE_AVAILABILITY=true`. Remote reason is included only when `EMAIL_INCLUDE_REMOTE_REASON=true`.

### Email Style

| Variable                               |        Default | Options                                                                                            | Description                                                          |
| -------------------------------------- | -------------: | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `EMAIL_LANGUAGE`                       |      `English` | Any language name                                                                                  | Output language. Examples: `English`, `Turkish`, `French`, `Arabic`. |
| `EMAIL_ACADEMIC_LEVEL`                 |            `B` | `A`, `B`, `C`                                                                                      | Formality level.                                                     |
| `EMAIL_TONE`                           | `professional` | `professional`, `warm`, `confident`, `humble`, `startup`, `research-focused`, `formal`, `friendly` | Tone hint.                                                           |
| `EMAIL_LENGTH`                         |       `medium` | `short`, `medium`, `long`                                                                          | Target length.                                                       |
| `EMAIL_MAX_WORDS`                      |          `350` | `80` to `700`                                                                                      | Hard maximum instruction. Values are clamped.                        |
| `EMAIL_FORMAT`                         |         `full` | `compact`, `full`                                                                                  | Email structure.                                                     |
| `EMAIL_GREETING_STYLE`                 |         `team` | `team`, `hiring-team`, `recruiter`, `formal`                                                       | Greeting preference.                                                 |
| `EMAIL_SIGNATURE_STYLE`                |      `compact` | `minimal`, `compact`, `detailed`                                                                   | Signature style.                                                     |
| `EMAIL_INCLUDE_SUBJECT_KEYWORDS`       |         `true` | `true`, `false`                                                                                    | Add one relevant keyword to subject.                                 |
| `EMAIL_INCLUDE_CV_ATTACHMENT_NOTE`     |         `true` | `true`, `false`                                                                                    | Mention attached CV.                                                 |
| `EMAIL_INCLUDE_UNIVERSITY_REQUIREMENT` |         `true` | `true`, `false`                                                                                    | Mention university requirement when available.                       |
| `EMAIL_INCLUDE_INSURANCE_NOTE`         |         `true` | `true`, `false`                                                                                    | Mention insurance when available.                                    |
| `EMAIL_INCLUDE_LINKS`                  |         `true` | `true`, `false`                                                                                    | Include links when available.                                        |
| `EMAIL_INCLUDE_PHONE`                  |        `false` | `true`, `false`                                                                                    | Include phone when available.                                        |
| `EMAIL_INCLUDE_LOCATION`               |        `false` | `true`, `false`                                                                                    | Include location when available.                                     |
| `EMAIL_INCLUDE_GPA`                    |        `false` | `true`, `false`                                                                                    | Include GPA when available.                                          |
| `EMAIL_INCLUDE_LANGUAGES`              |        `false` | `true`, `false`                                                                                    | Include languages when available.                                    |
| `EMAIL_INCLUDE_AVAILABILITY`           |        `false` | `true`, `false`                                                                                    | Include availability when available.                                 |
| `EMAIL_INCLUDE_REMOTE_REASON`          |         `true` | `true`, `false`                                                                                    | Include remote reason when available.                                |

Academic levels:

- `A`: simple, friendly, startup-style
- `B`: balanced professional
- `C`: formal, academic, research-oriented

Length guide:

- `short`: 150-220 words
- `medium`: 250-400 words
- `long`: 400-650 words

Signature styles:

- `minimal`: sign-off and name if available
- `compact`: name plus selected links on one concise line
- `detailed`: name, email, phone/location if enabled, and selected links

### Batch / Campaign

| Variable                      | Default | Options         | Description                                                             |
| ----------------------------- | ------: | --------------- | ----------------------------------------------------------------------- |
| `BATCH_DEFAULT_DELAY_SECONDS` |    `20` | integer         | Default delay between sends.                                            |
| `BATCH_DEFAULT_LIMIT`         |    `20` | integer         | Default maximum sends for `--send --yes` when no `--limit` is provided. |
| `BATCH_ALLOW_DUPLICATES`      | `false` | `true`, `false` | Allow duplicate rows by default.                                        |
| `BATCH_SKIP_EXISTING`         |  `true` | `true`, `false` | Skip already tracked applications.                                      |
| `BATCH_SAVE_DRAFTS`           |  `true` | `true`, `false` | Save local draft markdown files.                                        |

## Basic Usage

Preview only:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com
```

Preview and send after confirmation:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com --send
```

Save the final email-writing prompt and filtered config snapshot:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com --debug-prompt
```

Save raw, sanitized, parsed, and final LLM outputs:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com --debug-llm-output
```

Show loaded non-secret config:

```bash
python main.py config
```

Check Ollama:

```bash
python main.py check-llm
```

Benchmark the selected model:

```bash
python main.py benchmark-llm
```

Show application history:

```bash
python main.py history
```

## Sending Emails

Without `--send`, HUNT does not send email.

With `--send`, HUNT:

1. Generates the email.
2. Shows the preview.
3. Asks for confirmation.
4. Sends only after confirmation.
5. Attaches the CV.
6. Updates the tracker.

Sending uses Gmail SMTP over SSL on port `465`.

If SMTP credentials are missing or invalid, HUNT fails safely and shows a clear error. The generated email is still tracked.

## Draft-Only Workflow

Single `apply` mode is preview-first. If you do not pass `--send`, nothing is sent.

Batch mode saves local markdown drafts by default:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf
```

You can also be explicit:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf --draft-only
```

Current draft files are saved in `data/drafts/`. Dedicated draft browser commands are planned:

```bash
python main.py drafts
python main.py show-draft 1
```

Those commands are not implemented yet.

## Batch / Campaign Mode

Batch mode processes a CSV sequentially and safely. It is useful when you have a small list of companies and want a tailored draft for each one.

Required CSV columns:

- `website`
- `email`

Optional CSV columns:

- `company_name`
- `notes`
- `role`
- `language`
- `internship_mode`
- `status`

Example:

```csv
company_name,website,email,notes,role,language,internship_mode
Vispera,https://vispera.co,careers@vispera.co,Interested in computer vision and retail AI,AI Engineering Intern,English,remote
Pulse,https://runpulse.com,hello@runpulse.com,Interested in document AI and data extraction,ML Intern,English,remote
```

A sample file is included at `examples/companies.csv`.

Default draft-only batch:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf
```

Explicit draft-only batch:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf --draft-only
```

Validate the CSV without calling Ollama:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf --dry-run
```

Process only part of a CSV:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf --limit 10 --start-at 5
```

Send with confirmation per company:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf --send
```

Advanced send mode:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf --send --yes --limit 10 --delay 30
```

Custom results path:

```bash
python main.py batch --csv examples/companies.csv --cv ./cv.pdf --output data/my_batch_results.csv
```

Batch flags:

| Flag                 | Description                                                                              |
| -------------------- | ---------------------------------------------------------------------------------------- |
| `--send`             | Allows sending. Confirmation is still required per company unless `--yes` is also used.  |
| `--draft-only`       | Saves drafts locally and never sends.                                                    |
| `--yes`              | Advanced mode. Sends without per-company confirmation only after an extra typed warning. |
| `--limit 10`         | Maximum number of companies to process.                                                  |
| `--start-at 0`       | Start from a specific row index.                                                         |
| `--delay 30`         | Delay in seconds between sends.                                                          |
| `--skip-existing`    | Skip already tracked applications. Enabled by default.                                   |
| `--no-skip-existing` | Process rows even if they already appear in tracking.                                    |
| `--dry-run`          | Validate CSV and show what would be processed without calling Ollama.                    |
| `--output PATH`      | Save batch results to a custom CSV path.                                                 |
| `--allow-duplicates` | Process duplicate email/website rows.                                                    |
| `--use-cache`        | Reuse website extraction results within the run.                                         |

Safety behavior:

- Default mode does not send.
- `--send` asks per company.
- `--send --yes` requires typing `I UNDERSTAND`.
- `--send --yes` enforces a limit. If no `--limit` is provided, the default maximum is `20`.
- Batch mode processes sequentially.
- Delay is supported between sends.
- Duplicate rows are detected unless explicitly allowed.
- Invalid rows are skipped and logged.
- Results CSV is updated after every row.
- Low-quality generated output is not sent.
- Ctrl+C stops the batch gracefully and keeps progress saved where possible.

## Output And Data Files

| Path                             | Description                                                   |
| -------------------------------- | ------------------------------------------------------------- |
| `data/applications.db`           | SQLite application and batch tracking.                        |
| `data/drafts/`                   | Local markdown drafts from batch mode.                        |
| `data/debug/`                    | Raw, sanitized, parsed, and final LLM outputs when debugging. |
| `data/last_prompt.txt`           | Final email-writing prompt from `--debug-prompt`.             |
| `data/last_config_snapshot.json` | Filtered prompt config from `--debug-prompt`.                 |
| `data/batch_results.csv`         | Default batch progress/results file.                          |

These files may contain personal information and should generally not be committed.

## Troubleshooting

### `.env` Changes Are Not Applying

Run:

```bash
python main.py config
```

Check:

- loaded `.env` path
- selected Ollama model
- email language and style settings
- profile fields passed to the LLM
- signature fields passed to the LLM
- internship fields passed to the LLM

Make sure:

- the file is named `.env`, not `.env.example`
- `.env` is in the project root
- you saved the file after editing
- the variable name has no typo

HUNT reloads `.env` each time `load_config()` runs and uses `override=True`, so recent changes should be visible in `python main.py config`.

### SMTP Credentials Are Missing

HUNT reads `.env`, not `.env.example`.

```bash
cp .env.example .env
```

Then edit:

```env
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=your_gmail_app_password
```

Do not commit `.env`.

### Gmail App Password Setting Is Unavailable

Common reasons:

- 2-Step Verification is not enabled.
- The account is managed by a school or workplace.
- The account uses Advanced Protection.
- The account is configured for security-key-only sign-in.

Options:

- use preview mode
- use batch draft-only mode
- use a personal Gmail account that supports app passwords
- wait for a future Gmail OAuth mode

### Ollama Connection Failed

Start Ollama:

```bash
ollama serve
```

Check the local API:

```bash
curl http://localhost:11434/api/tags
```

Then run:

```bash
python main.py check-llm
```

### Ollama Request Timed Out Or Feels Slow

Use a smaller model:

```env
OLLAMA_MODEL=qwen2.5:3b-instruct
```

Also try:

- a shorter CV
- a company `/about` page instead of a heavy homepage
- closing other memory-heavy apps
- using `qwen2.5:3b-instruct` instead of a 7B model

Planned tuning knobs:

```env
OLLAMA_TIMEOUT_SECONDS=300
OLLAMA_NUM_CTX=4096
OLLAMA_MAX_WEBSITE_CHARS=4000
OLLAMA_MAX_CV_CHARS=6000
OLLAMA_USE_FAST_MODE=true
OLLAMA_SKIP_SUMMARIZATION=true
```

These planned variables are documented for the intended roadmap. The current implementation does not read them yet.

### Output Is Not Valid JSON Or The Email Looks Messy

Local models sometimes return markdown, code fences, control tokens, or text around JSON. HUNT includes JSON repair, nested JSON unwrapping, and output sanitization.

Recommended steps:

```bash
python main.py apply --website https://company.com --cv ./cv.pdf --email careers@company.com --debug-llm-output
```

Then inspect:

- `data/debug/email_raw.txt`
- `data/debug/email_sanitized.txt`
- `data/debug/email_parsed.json`
- `data/debug/email_final.txt`

Try:

- `qwen2.5:3b-instruct`
- `qwen2.5:7b-instruct`
- a shorter CV
- a smaller company page
- avoiding reasoning-focused models for strict JSON output

### CV Cannot Be Read

Supported formats:

- PDF
- DOCX
- TXT

If a scanned PDF has no embedded text, convert it with OCR first.

### Website Cannot Be Read

Some websites block scraping. Try:

- the company homepage
- a careers page
- an about page
- a simpler product page

## Privacy And Security

- Your CV stays local unless you send it as an email attachment.
- Website text is public company data.
- The LLM runs locally through Ollama.
- No OpenAI or cloud LLM key is required.
- Gmail SMTP is used only when you enable sending.
- `.env.example` is safe to commit only when it contains placeholders.
- `.env` is private and must never be committed.
- Revoke leaked app passwords immediately.

## Ethical Use

HUNT is for personalized internship outreach, not spam.

You should:

- review emails before sending
- respect company contact policies
- apply only to relevant opportunities
- avoid misleading or fake claims
- avoid sending unwanted mass messages
- never invent experience

Batch mode is intentionally sequential, limited, and confirmation-first so the user remains responsible for every message.

## Development Guide

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
python -m unittest discover -s tests
```

`pytest` can also run many `unittest`-style test suites if it is installed:

```bash
pytest
```

Project structure:

```text
HUNT/
  hunt/
    __init__.py
    cli.py
    config.py
    website_reader.py
    cv_reader.py
    local_llm.py
    email_writer.py
    json_utils.py
    email_sender.py
    tracker.py
    batch.py
    utils.py
  data/
    applications.db
  examples/
    companies.csv
  tests/
  .env.example
  requirements.txt
  README.md
  main.py
```

File overview:

| File                     | Purpose                                    |
| ------------------------ | ------------------------------------------ |
| `hunt/cli.py`            | Typer CLI commands and Rich output.        |
| `hunt/config.py`         | `.env` loading and typed configuration.    |
| `hunt/website_reader.py` | Website text extraction.                   |
| `hunt/cv_reader.py`      | PDF, DOCX, and TXT CV parsing.             |
| `hunt/local_llm.py`      | Ollama API calls.                          |
| `hunt/email_writer.py`   | Prompt building and email generation flow. |
| `hunt/json_utils.py`     | JSON repair, sanitization, and validation. |
| `hunt/email_sender.py`   | Gmail SMTP sending.                        |
| `hunt/tracker.py`        | SQLite tracking.                           |
| `hunt/batch.py`          | CSV batch processing.                      |
| `hunt/utils.py`          | Shared utilities.                          |
| `main.py`                | CLI entry point.                           |

## Testing

Run:

```bash
python -m unittest discover -s tests
```

Tests cover:

- config parsing
- `.env` loading
- optional field filtering
- JSON repair and sanitization
- CV reader behavior
- email parsing
- tracker behavior
- CLI preview safety
- batch CSV validation and safety behavior

## License

HUNT is released under the MIT License. See [LICENSE](LICENSE) for details.

## Roadmap

- Gmail OAuth
- More email providers
- Explicit draft browser commands
- Better company email finder
- Batch/campaign improvements
- Draft editing
- Web UI
- Persistent company cache
- Follow-up generator
- Cover letter generation
- Application analytics
- Fast one-call generation mode
- Configurable Ollama timeout and context settings

## FAQ

### Does HUNT Use OpenAI?

No. HUNT uses local Ollama models.

### Is My CV Uploaded To The Cloud?

No, not for generation. Your CV stays local unless you choose to send it as an email attachment.

### Can I Use Another Local Model?

Yes. Set `OLLAMA_MODEL` to any model installed in Ollama.

### Why Is Ollama Slow?

The model may be too large, or the website/CV prompt may be too long. Use `qwen2.5:3b-instruct` on low-resource machines.

### Can I Use HUNT Without Sending Emails?

Yes. Omit `--send`, or use batch draft-only mode.

### Can I Generate eails in another language?

Yes. Set:

```env
EMAIL_LANGUAGE=prefered_language
```

### What Is Academic Level A/B/C?

- `A`: simple and friendly
- `B`: balanced professional
- `C`: formal and academic

## Important

HUNT should be used as an ethical internship outreach assistant, not as a spam or mass-mailing tool. Users should only contact companies they are genuinely interested in, review every generated email before sending, and make sure each message is accurate, respectful, and personalized to the company. HUNT must never be used to invent experience, misrepresent qualifications, bypass company application systems, or send high-volume unsolicited emails. The goal is to help students communicate their real skills and interests more clearly while respecting recruiters’ time, company contact policies, and basic professional honesty.
