# Resume Toolkit

A two-part toolkit for generating and improving a structured resume using the Claude API.

---

## Structure

```
JobSwitch/
├── resume_data.example.json   # schema template — copy to resume_data.json and fill in
├── generate_resume.py         # generates PDF + DOCX from resume_data.json
├── ResumeEditor/
│   ├── judge.py               # panel of 3 LLM judges (recruiter, hiring manager, AI detector)
│   ├── editor.py              # LLM editor — proposes diffs based on judge feedback
│   ├── prompts/               # system prompts for each judge persona + editor
│   ├── smoke_test.py          # verifies API key and SDK are working
│   ├── requirements.txt       # pinned dependencies
│   └── .env.example           # copy to .env and add your API key
```

---

## Setup

```bash
# 1. Clone and enter the project
cd JobSwitch

# 2. Copy and fill in your resume data
cp resume_data.example.json resume_data.json
# Edit resume_data.json with your actual content

# 3. Set up the Python environment
cd ResumeEditor
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. Add your Anthropic API key
cp .env.example .env
# Edit .env and replace the placeholder with your real key
# Get a key at: console.anthropic.com

# 5. Verify the setup
python3 smoke_test.py           # should print: SDK working.
```

---

## Generating a resume

```bash
cd JobSwitch

# Base resume (saves to JobSwitch/)
python3 generate_resume.py

# Company-specific (saves to Company Resume/<CompanyName>/)
python3 generate_resume.py "Google"
python3 generate_resume.py "Google" --pdf-only
python3 generate_resume.py "Google" --docx-only
```

---

## Running the judge + editor loop

```bash
cd ResumeEditor
source venv/bin/activate

# Step 1 — judge the base resume (saves judge_output.json)
python3 judge.py

# Step 2 — run editor (review and approve each proposed edit)
python3 editor.py                        # base resume — prompts to save a versioned PDF snapshot
python3 editor.py --company "Google"     # generates PDF + DOCX in Company Resume/Google/

# The editor will ask at the end if you want to re-run the judge to see score delta.
```

### Base resume versioning

When running `editor.py` without `--company`, you'll be asked if you want to save a PDF snapshot. These are saved as:

```
Company Resume/BaseResumeVersion/BaseResume_May_2026_v1.pdf
Company Resume/BaseResumeVersion/BaseResume_May_2026_v2.pdf
...
```

---

## How the judge works

Three personas evaluate the resume in parallel:

| Persona | What it checks |
|---|---|
| **Recruiter** | Catchiness, summary hook, ATS signal, scannability |
| **Hiring Manager** | Seniority signal, impact credibility, technical depth, ownership clarity |
| **AI Detector** | Human authenticity, buzzword density, specificity, voice consistency |

Each persona returns a score (1–5) per dimension, flagged phrases, and top 3 fixes. Results are aggregated into a single report with an overall average score.

---

## What the editor will and won't change

**Will change:** summary phrasing, bullet verb strength, soft ownership language, buzzword density

**Will never change:** any metric or number, bullet count per role, company/title/dates, education, or anything not already in the resume

---

## Requirements

- Python 3.11+
- Anthropic API key with credits ([console.anthropic.com](https://console.anthropic.com))
- `python-docx` and `reportlab` (for `generate_resume.py` — install separately if needed)
