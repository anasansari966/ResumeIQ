"""
ResumeIQ - Smart Job Matcher
=============================
Reads your resume PDF → Extracts profile via OpenAI →
Searches jobs via JobSpy (LinkedIn, Indeed, Glassdoor) + Naukri RSS →
Filters only suitable matches → Displays results

Requirements:
    pip install python-jobspy pdfplumber openai pandas rich python-dotenv feedparser
"""

import json
import os
from pathlib import Path

import feedparser
import pdfplumber
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from jobspy import scrape_jobs
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / "backend" / ".env", override=True)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
RESUME_PATH = "Anas_Resume.pdf"
OPENAI_API_KEY = (os.environ.get("OPENAI_API_KEY") or "").strip() or "YOUR_OPENAI_API_KEY"
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
LOCATION = "India"          # ← Change if needed (e.g. "Delhi", "Bangalore")
RESULTS_WANTED = 50         # Jobs to fetch before filtering
MIN_MATCH_SCORE = 60        # Only show jobs with score >= 60%

console = Console()


# ─────────────────────────────────────────────
# STEP 1: Extract text from PDF
# ─────────────────────────────────────────────
def extract_resume_text(pdf_path: str) -> str:
    console.print(f"\n[bold cyan]📄 Reading resume:[/] {pdf_path}")
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    if not text.strip():
        raise ValueError("Could not extract text from PDF. Make sure it's not a scanned image.")
    console.print(f"[green]✓ Extracted {len(text)} characters from resume[/]")
    return text


# ─────────────────────────────────────────────
# HELPER: OpenAI JSON call
# ─────────────────────────────────────────────
def _openai_json_text(client: OpenAI, prompt: str, max_tokens: int) -> str:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    choice = response.choices[0].message
    raw = (choice.content or "").strip()
    if not raw:
        raise ValueError("OpenAI returned an empty response")
    return raw


def _clean_json(raw: str) -> str:
    """Strip markdown code fences if model adds them."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ─────────────────────────────────────────────
# STEP 2: Parse resume with OpenAI
# ─────────────────────────────────────────────
def parse_resume_with_openai(resume_text: str) -> dict:
    console.print("\n[bold cyan]🤖 Analyzing resume with OpenAI...[/]")

    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
You are a resume parser. Extract structured information from this resume.

Return ONLY a valid JSON object with these exact keys:
{{
  "full_name": "candidate's full name",
  "primary_job_title": "most suitable job title (e.g. Data Scientist, Backend Developer)",
  "alternative_titles": ["2-3 related job titles to also search for"],
  "skills": ["list of top 10 technical skills"],
  "years_of_experience": 2,
  "experience_level": "fresher|junior|mid|senior",
  "education": "highest qualification (e.g. B.Tech Computer Science)",
  "preferred_location": "city or remote",
  "job_search_keywords": ["3-5 short search terms to use in job boards"],
  "summary": "2-line profile summary"
}}

Rules:
- years_of_experience must be a number
- experience_level: fresher=0-1yr, junior=1-3yr, mid=3-6yr, senior=6+yr
- job_search_keywords must be SHORT (1-3 words each), suitable for job board search
- Return ONLY the JSON, no explanation, no markdown backticks

RESUME TEXT:
{resume_text}
"""

    raw = _clean_json(_openai_json_text(client, prompt, max_tokens=1000))
    profile = json.loads(raw)

    console.print(
        f"[green]✓ Profile extracted:[/] {profile['full_name']} | "
        f"{profile['primary_job_title']} | {profile['years_of_experience']} yrs exp"
    )
    return profile


# ─────────────────────────────────────────────
# STEP 3a: Naukri RSS scraper (no captcha)
# ─────────────────────────────────────────────
def scrape_naukri_rss(keyword: str, location: str = "india") -> pd.DataFrame:
    """
    Fetch jobs from Naukri's public RSS feed.
    No API key needed, no reCAPTCHA, always works.
    """
    keyword_slug  = keyword.lower().replace(" ", "-")
    location_slug = location.lower().replace(" ", "-")
    url = f"https://www.naukri.com/rss/{keyword_slug}-jobs-in-{location_slug}.rss"

    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            console.print(f"     [yellow]Naukri RSS → No entries found for '{keyword}'[/]")
            return pd.DataFrame()

        jobs = []
        for entry in feed.entries:
            jobs.append({
                "title":          entry.get("title", ""),
                "company":        entry.get("author", ""),
                "location":       location.title(),
                "job_url":        entry.get("link", ""),
                "description":    entry.get("summary", ""),
                "date_posted":    entry.get("published", ""),
                "site":           "naukri",
                "search_keyword": keyword,
            })

        df = pd.DataFrame(jobs)
        console.print(f"     [green]Naukri RSS → Found {len(df)} jobs[/]")
        return df

    except Exception as e:
        console.print(f"     [yellow]Naukri RSS warning: {e}[/]")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# STEP 3b: Search all sources
# ─────────────────────────────────────────────
def search_jobs(profile: dict) -> pd.DataFrame:
    console.print(
        "\n[bold cyan]🔍 Searching LinkedIn, Indeed, Glassdoor + Naukri RSS...[/]"
    )

    all_jobs     = []
    keywords     = profile.get("job_search_keywords", [profile["primary_job_title"]])
    top_keywords = keywords[:3]  # limit to 3 to avoid rate-limits

    for keyword in top_keywords:
        console.print(f"  → Searching: [yellow]{keyword}[/]")

        # ── JobSpy: LinkedIn + Indeed + Glassdoor ──
        # NOTE: Naukri removed from JobSpy — throws 406 reCAPTCHA errors.
        #       We use Naukri RSS below instead.
        try:
            jobs = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=keyword,
                location=LOCATION,
                results_wanted=RESULTS_WANTED // len(top_keywords),
                hours_old=168,           # Last 7 days
                country_indeed="India",
                linkedin_fetch_description=True,
            )
            if not jobs.empty:
                jobs["search_keyword"] = keyword
                all_jobs.append(jobs)
                console.print(f"     [green]JobSpy → Found {len(jobs)} jobs[/]")
        except Exception as e:
            console.print(f"     [red]JobSpy error for '{keyword}': {e}[/]")

        # ── Naukri via RSS (no captcha) ──
        naukri_df = scrape_naukri_rss(keyword, LOCATION)
        if not naukri_df.empty:
            all_jobs.append(naukri_df)

    if not all_jobs:
        console.print("[red]❌ No jobs found from any source.[/]")
        return pd.DataFrame()

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["title", "company"], keep="first")
    console.print(f"\n[green]✓ Total unique jobs fetched: {len(combined)}[/]")
    return combined


# ─────────────────────────────────────────────
# STEP 4: Score jobs with OpenAI
# ─────────────────────────────────────────────
def score_jobs_with_openai(jobs_df: pd.DataFrame, profile: dict) -> list:
    console.print(f"\n[bold cyan]🎯 Scoring {len(jobs_df)} jobs for suitability...[/]")

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Lightweight job list — truncate description to save tokens
    jobs_list = []
    for _, row in jobs_df.iterrows():
        desc = str(row.get("description", ""))[:500] if pd.notna(row.get("description")) else ""
        jobs_list.append({
            "id":                   int(row.name),
            "title":                str(row.get("title", "")),
            "company":              str(row.get("company", "")),
            "location":             str(row.get("location", "")),
            "description_snippet":  desc,
        })

    batch_size     = 15
    scored_results = []
    total_batches  = max(1, (len(jobs_list) - 1) // batch_size + 1)

    for i in range(0, len(jobs_list), batch_size):
        batch     = jobs_list[i:i + batch_size]
        batch_num = i // batch_size + 1
        console.print(f"  → Scoring batch {batch_num}/{total_batches} ({len(batch)} jobs)")

        prompt = f"""
You are a job-matching expert. Score each job's suitability for this candidate.

CANDIDATE PROFILE:
- Name: {profile['full_name']}
- Target Role: {profile['primary_job_title']}
- Skills: {', '.join(profile['skills'][:10])}
- Experience: {profile['years_of_experience']} years ({profile['experience_level']} level)
- Education: {profile['education']}

JOBS TO SCORE:
{json.dumps(batch, indent=2)}

For each job, return a JSON array. Each element must have:
{{
  "id": <same id as input>,
  "match_score": <integer 0-100>,
  "match_reason": "<one sentence why it matches or doesn't>",
  "missing_skills": ["skill1", "skill2"],
  "verdict": "excellent|good|fair|poor"
}}

Scoring guide:
- 80-100: Excellent match — title and skills align perfectly
- 60-79:  Good match — mostly relevant with minor gaps
- 40-59:  Fair — related but significant skill/experience gaps
- 0-39:   Poor — not relevant

Return ONLY the JSON array, no markdown, no explanation.
"""

        try:
            raw          = _clean_json(_openai_json_text(client, prompt, max_tokens=2000))
            batch_scores = json.loads(raw)
            scored_results.extend(batch_scores)
        except Exception as e:
            console.print(f"     [red]Scoring error: {e}[/]")
            # Fallback: neutral score so the job still surfaces for manual review
            for job in batch:
                scored_results.append({
                    "id":             job["id"],
                    "match_score":    50,
                    "match_reason":   "Could not score — review manually",
                    "missing_skills": [],
                    "verdict":        "fair",
                })

    return scored_results


# ─────────────────────────────────────────────
# STEP 5: Merge scores + filter + display
# ─────────────────────────────────────────────
def display_results(jobs_df: pd.DataFrame, scores: list, profile: dict, min_score: int):
    score_map = {s["id"]: s for s in scores}

    jobs_df["match_score"]    = jobs_df.index.map(lambda i: score_map.get(i, {}).get("match_score", 0))
    jobs_df["match_reason"]   = jobs_df.index.map(lambda i: score_map.get(i, {}).get("match_reason", ""))
    jobs_df["missing_skills"] = jobs_df.index.map(lambda i: score_map.get(i, {}).get("missing_skills", []))
    jobs_df["verdict"]        = jobs_df.index.map(lambda i: score_map.get(i, {}).get("verdict", "fair"))

    suitable = jobs_df[jobs_df["match_score"] >= min_score].sort_values(
        "match_score", ascending=False
    )

    console.print(f"\n[green]✓ Found {len(suitable)} suitable jobs (score ≥ {min_score}%)[/]")

    if suitable.empty:
        console.print(
            "[yellow]No jobs met the minimum match threshold. "
            "Try lowering MIN_MATCH_SCORE in the config.[/]"
        )
        return

    # ── Candidate summary ──
    rprint(Panel(
        f"[bold white]{profile['full_name']}[/] | {profile['primary_job_title']} | "
        f"{profile['years_of_experience']} yrs | {profile['education']}\n"
        f"[dim]Skills: {', '.join(profile['skills'][:6])}[/]",
        title="[bold green]🧠 ResumeIQ — Matched Jobs",
        border_style="green",
    ))

    # ── Results table ──
    table = Table(
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        row_styles=["", "dim"],
        expand=True,
    )
    table.add_column("#",              style="dim", width=3)
    table.add_column("Match",          width=8,     justify="center")
    table.add_column("Job Title",      min_width=25)
    table.add_column("Company",        min_width=18)
    table.add_column("Location",       min_width=15)
    table.add_column("Source",         width=10)
    table.add_column("Why it matches", min_width=35)

    verdict_colors = {
        "excellent": "bold green",
        "good":      "green",
        "fair":      "yellow",
        "poor":      "red",
    }

    for rank, (_, row) in enumerate(suitable.iterrows(), 1):
        score   = int(row["match_score"])
        verdict = row.get("verdict", "fair")
        color   = verdict_colors.get(verdict, "white")

        filled     = score // 10
        bar        = "█" * filled + "░" * (10 - filled)
        score_text = Text(f"{score}%\n{bar[:5]}", style=color)
2
        table.add_row(
            str(rank),
            score_text,
            str(row.get("title",        "N/A")),
            str(row.get("company",      "N/A")),
            str(row.get("location",     "N/A"))[:20],
            str(row.get("site",         "N/A")),
            str(row.get("match_reason", ""))[:65],
        )

    console.print(table)

    # ── Top 5 detailed cards ──
    console.print("\n[bold cyan]📋 Top 5 Job Details:[/]")
    for rank, (_, row) in enumerate(suitable.head(5).iterrows(), 1):
        missing     = row.get("missing_skills", [])
        missing_str = ", ".join(missing) if missing else "None — you're fully qualified!"
        url         = row.get("job_url", "N/A")

        rprint(Panel(
            f"[bold white]{row.get('title')}[/] @ [cyan]{row.get('company')}[/]\n"
            f"📍 {row.get('location')}  |  🌐 {row.get('site')}  |  📅 {row.get('date_posted', 'N/A')}\n\n"
            f"[green]✅ Why you match:[/] {row.get('match_reason')}\n"
            f"[yellow]⚠️  Missing skills:[/] {missing_str}\n\n"
            f"[dim]🔗 {url}[/]",
            title=f"[bold green]#{rank} — {int(row['match_score'])}% Match[/]",
            border_style="green" if row["match_score"] >= 80 else "yellow",
        ))

    # ── Save CSV ──
    output_file = "matched_jobs.csv"
    suitable[[
        "title", "company", "location", "site",
        "match_score", "verdict", "match_reason",
        "job_url", "date_posted",
    ]].to_csv(output_file, index=False)
    console.print(f"\n[bold green]✅ Results saved to:[/] {output_file}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    console.print(Panel.fit(
        "[bold white]ResumeIQ — Smart Job Matcher[/]\n"
        "[dim]Powered by JobSpy + Naukri RSS + OpenAI[/]",
        border_style="cyan",
    ))

    try:
        resume_text = extract_resume_text(RESUME_PATH)
        profile     = parse_resume_with_openai(resume_text)
        jobs_df     = search_jobs(profile)

        if jobs_df.empty:
            return

        scores = score_jobs_with_openai(jobs_df, profile)
        display_results(jobs_df, scores, profile, MIN_MATCH_SCORE)

    except FileNotFoundError:
        console.print(f"[red]❌ Resume not found at path: {RESUME_PATH}[/]")
        console.print("[yellow]Make sure Anas_Resume.pdf is in the same folder as this script.[/]")
    except json.JSONDecodeError as e:
        console.print(f"[red]❌ Failed to parse OpenAI's response as JSON: {e}[/]")
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/]")
        raise


if __name__ == "__main__":
    main()