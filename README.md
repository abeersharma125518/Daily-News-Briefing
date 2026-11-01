# Daily News Briefing

A Python pipeline that pulls RSS feeds from across the political spectrum, clusters stories covering the same event, and emails you a single HTML briefing with **paired opposing-source coverage** of each story.

Instead of reading one outlet's framing of an event, you see how the left, right, and center each covered it — side by side.

## What it produces

Each briefing has three parts:

| Part | Content |
|------|---------|
| **1. Headlines** | Top articles per category, grouped by topic |
| **2. Deep Dive** | Topic clusters where *multiple sources* covered the same story, with an LLM-written analysis of how their framing differs |
| **3. Intelligence** | Per-category synthesis: what matters today, what's being under-reported, what narratives are forming |

Output is a self-contained HTML email. Categories ship configured for World/US, India, Technology, Business, and Science — all editable in `config.yaml`.

## How it works

```
RSS feeds ──> fetch ──> dedupe (state.json) ──> semantic clustering ──> Ollama analysis ──> HTML ──> email
```

1. **Fetch** (`fetcher.py`) — pulls all RSS sources in parallel, with retries.
2. **Dedupe** (`state.py`) — skips anything already sent, so you never get repeats.
3. **Cluster** (`matcher.py`) — embeds headlines/titles and groups them by cosine similarity above a configurable threshold, requiring a minimum number of distinct sources.
4. **Analyze** (`analyzer.py`, `intelligence.py`) — a local Ollama model compares framing across sources and writes the deep-dive and intelligence sections.
5. **Format** (`formatter.py`) — renders a responsive Jinja2 HTML briefing.
6. **Deliver** (`deliverer.py`) — sends via SMTP, or saves to `briefings/` if email isn't configured.

## Requirements

- **Python 3.10+** (tested on 3.14)
- **Ollama** (optional but recommended) — for the analysis and intelligence sections. The pipeline degrades gracefully without it: headlines still generate, and Part 2/3 are simply skipped.
- A **Gmail account with an App Password** to receive the email.

## Setup

```powershell
git clone https://github.com/abeersharma125518/Daily-News-Briefing.git
cd Daily-News-Briefing

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then run it once to generate your config file:

```powershell
python main.py
```

On first run this copies `config.example.yaml` to `config.yaml` and exits. Open `config.yaml` and fill in:

```yaml
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender: "you@gmail.com"
  password: "your-16-char-app-password"   # NOT your normal password
  recipient: "you@gmail.com"
```

> **Getting an app password:** Google requires 2-Step Verification first, then visit <https://myaccount.google.com/apppasswords>. If you paste your regular account password, SMTP auth will fail with an error.

### Optional: local LLM

Install [Ollama](https://ollama.com), then pull a model:

```powershell
ollama pull llama3.2
```

Point `config.yaml` at it if needed:

```yaml
ollama:
  model: "llama3.2"
  base_url: "http://localhost:11434"
  temperature: 0.3
```

Without Ollama running, the pipeline logs a warning and continues — you just lose the analysis sections.

## Usage

```powershell
# Send the briefing by email
python main.py

# Save the HTML locally instead of emailing
python main.py --output briefing.html

# Skip the LLM entirely (fast, headlines only)
python main.py --no-analyze

# Skip just the Part 3 intelligence synthesis
python main.py --no-intel

# Send even when no topic clusters form
python main.py --force

# Change how many stories per category
python main.py --max-triads 3
```

| Flag | Description |
|------|-------------|
| `--config PATH` | Use a different config file (default `config.yaml`) |
| `--output PATH`, `-o` | Write HTML to a file instead of sending email |
| `--no-analyze` | Skip all LLM work |
| `--no-intel` | Skip Part 3 intelligence synthesis |
| `--max-triads N` | Max clustered stories per category |
| `--log-file PATH` | Also write logs to a file |
| `--verbose`, `-v` | Debug logging |
| `--force` | Send even with no clusters |

Exit codes: `0` success, `1` config problem, `2` fetch failure, `3` email failed after retries, `4` email not sent.

## Daily automation (Windows)

`setup_scheduler.ps1` registers a Task Scheduler job that runs every morning at 8:00 AM IST. It runs under SYSTEM (no login needed), retries up to 3 times 15 minutes apart, and logs to `logs/`.

```powershell
# Run from the project folder, in an elevated PowerShell
.\setup_scheduler.ps1
```

Or just double-click `run_manually.bat` for an ad-hoc run — you may need to fix the hardcoded Python path in that file first.

## Configuration

Everything is driven by `config.yaml`. Key sections:

- **`categories`** — add or remove categories, each with a list of `sources` (name, `bias`, RSS `rss` URL). Bias labels drive the left/right/center comparison.
- **`matching`** — clustering tuning: `similarity_threshold`, `min_sources_for_triad`, `max_articles_per_source_per_category`, `max_triads_per_category`.
- **`ollama`** — model, base URL, temperature.
- **`email`** — SMTP settings.

To add a source, append to any category's `sources` list:

```yaml
- name: "The Guardian"
  bias: "left"
  rss: "https://www.theguardian.com/world/rss"
```

Lower `similarity_threshold` to cluster more aggressively; raise it for stricter matching.

## Project layout

| File | Role |
|------|------|
| `main.py` | Entry point, pipeline orchestration, CLI |
| `fetcher.py` | RSS fetching and parsing |
| `matcher.py` | Embedding-based topic clustering |
| `analyzer.py` | Per-cluster framing analysis via Ollama |
| `intelligence.py` | Cross-category synthesis (Part 3) |
| `formatter.py` | Jinja2 HTML rendering |
| `deliverer.py` | SMTP sending / local save |
| `state.py` | Sent-article tracking (`state.json`) |
| `config.example.yaml` | Config template with placeholder credentials |
| `setup_scheduler.ps1` | Windows Task Scheduler setup |
| `run_manually.bat` | Manual run helper |

## Notes

- **`config.yaml` is gitignored** — it holds your email password. Commit `config.example.yaml` instead, never the real one.
- **`state.json` is gitignored** — it's runtime state, regenerated as the pipeline runs.
- **`__pycache__/`, `logs/`, `briefings/`** are ignored.
- If email isn't configured, the briefing is saved to `briefings/` and the run exits cleanly, which is handy for trying it out.

## License

No license specified yet. If you want others to reuse this, add one — MIT is a reasonable default.
