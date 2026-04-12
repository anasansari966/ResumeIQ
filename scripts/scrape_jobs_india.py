#!/usr/bin/env python3
"""
Terminal demo: scrape Indeed India job listings (HTML only — no job APIs),
match against your resume text, print ALL eligible jobs in pages of N (default 20).

IMPORTANT
- Respect https://in.indeed.com/robots.txt and Indeed Terms of Use. This is for
  personal/educational use; commercial use may require permission.
- Sites change HTML often — if parsing breaks, update selectors.
- Use --delay to avoid hammering servers (default 2s between requests).

Usage (from repo root or anywhere):
  pip install -r scripts/requirements-scrape.txt
  python scripts/scrape_jobs_india.py --resume path/to/resume.pdf --query "data scientist" --location "Delhi, India"
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

BASE = "https://in.indeed.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass
class JobStub:
    jk: str
    title: str
    company: str
    location: str
    job_link: str


def extract_resume_text(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise SystemExit("Install pypdf: pip install pypdf") from e
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    if suf in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    raise SystemExit(f"Unsupported resume type: {suf} (use .pdf or .txt)")


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#./]{1,}", (text or "").lower()))


def eligibility_score(resume_text: str, jd: str, title: str = "", company: str = "") -> float:
    """
    Overlap-based score in [0, 1]: how much of the job text's distinct tokens
    appear in the resume (good proxy without ML deps).
    """
    blob = f"{title} {company} {jd}"
    r = tokenize(resume_text)
    j = tokenize(blob)
    if not j:
        return 0.0
    inter = len(r & j)
    # Favor recall into JD: matched tokens / JD tokens, capped by resume coverage
    recall = inter / len(j)
    precision = inter / max(1, len(r))
    return min(1.0, 0.55 * recall + 0.45 * precision)


def _client_headers() -> dict[str, str]:
    return {"User-Agent": DEFAULT_UA, "Accept-Language": "en-IN,en;q=0.9"}


def extract_jk_from_href(href: str) -> str | None:
    if not href:
        return None
    qs = parse_qs(urlparse(href).query)
    if "jk" in qs and qs["jk"]:
        return qs["jk"][0]
    m = re.search(r"[?&]jk=([^&]+)", href)
    return m.group(1) if m else None


def parse_list_page(html: str) -> list[JobStub]:
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, JobStub] = {}

    # Strategy A: anchor with data-jk (common on Indeed)
    for a in soup.select("a[data-jk]"):
        jk = (a.get("data-jk") or "").strip()
        if not jk:
            continue
        title = a.get_text(" ", strip=True) or "Untitled"
        job_link = f"{BASE}/viewjob?jk={jk}"
        card = a.find_parent("div", class_=re.compile(r"job_seen_beacon|slider|card", re.I)) or a.parent
        company, loc = "", ""
        if card:
            cn = card.select_one('[data-testid="company-name"], .companyName, span[class*="company"]')
            if cn:
                company = cn.get_text(" ", strip=True)
            loc_el = card.select_one('[data-testid="text-location"], .companyLocation, div[class*="location"]')
            if loc_el:
                loc = loc_el.get_text(" ", strip=True)
        seen[jk] = JobStub(jk=jk, title=title, company=company, location=loc, job_link=job_link)

    # Strategy B: any link containing jk= in href
    for a in soup.select('a[href*="jk="]'):
        href = a.get("href") or ""
        jk = extract_jk_from_href(href)
        if not jk or jk in seen:
            continue
        title = a.get_text(" ", strip=True) or "Untitled"
        if len(title) < 3:
            continue
        job_link = f"{BASE}/viewjob?jk={jk}"
        seen[jk] = JobStub(jk=jk, title=title, company="", location="", job_link=job_link)

    return list(seen.values())


def fetch_job_description(client: httpx.Client, jk: str, delay: float) -> str:
    time.sleep(delay)
    url = f"{BASE}/viewjob?jk={jk}"
    r = client.get(url, headers=_client_headers(), follow_redirects=True, timeout=45.0)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    box = soup.select_one(
        "#jobDescriptionText, div#jobDescriptionText, div.jobsearch-JobComponent-description"
    )
    if box:
        return box.get_text("\n", strip=True)
    return ""


def fetch_list_page(client: httpx.Client, query: str, location: str, start: int, delay: float) -> str:
    time.sleep(delay)
    url = f"{BASE}/jobs?q={quote_plus(query)}&l={quote_plus(location)}&start={start}"
    r = client.get(url, headers=_client_headers(), follow_redirects=True, timeout=45.0)
    r.raise_for_status()
    return r.text


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape Indeed India + resume match (terminal, no APIs).")
    ap.add_argument("--resume", type=Path, required=True, help="Resume .pdf or .txt")
    ap.add_argument("--query", default="software engineer", help="Indeed search query")
    ap.add_argument("--location", default="India", help='Indeed "where" (e.g. Delhi, India)')
    ap.add_argument("--threshold", type=float, default=0.12, help="Min eligibility score 0..1")
    ap.add_argument("--per-page", type=int, default=20, help="Jobs printed per output page")
    ap.add_argument("--max-list-pages", type=int, default=40, help="Max Indeed list pages (start+=10 each)")
    ap.add_argument("--max-detail", type=int, default=500, help="Max job detail pages to fetch (cap load)")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between HTTP requests")
    args = ap.parse_args()

    if not args.resume.is_file():
        sys.exit(f"Resume not found: {args.resume}")

    resume_text = extract_resume_text(args.resume)
    if len(resume_text.strip()) < 50:
        sys.exit("Resume text is very short — check PDF extraction.")

    print("Resume loaded:", len(resume_text), "chars")
    print("Search:", args.query, "|", args.location)
    print("Threshold:", args.threshold, "| delay:", args.delay, "s\n")

    stubs: list[JobStub] = []
    with httpx.Client() as client:
        for page_idx in range(args.max_list_pages):
            start = page_idx * 10  # Indeed uses steps of ~10
            try:
                html = fetch_list_page(client, args.query, args.location, start, args.delay)
            except Exception as e:
                print(f"List page start={start} failed: {e}", file=sys.stderr)
                break
            batch = parse_list_page(html)
            if not batch:
                print(f"No jobs parsed at start={start} — stopping list crawl.")
                break
            # De-dupe jk globally
            known = {s.jk for s in stubs}
            for b in batch:
                if b.jk not in known:
                    known.add(b.jk)
                    stubs.append(b)
            print(f"List page {page_idx + 1}: +{len(batch)} parsed (total stubs {len(stubs)})")

        eligible: list[tuple[JobStub, float, str]] = []
        for i, stub in enumerate(stubs[: args.max_detail]):
            try:
                jd = fetch_job_description(client, stub.jk, args.delay)
            except Exception as e:
                print(f"  skip jk={stub.jk}: {e}", file=sys.stderr)
                continue
            score = eligibility_score(resume_text, jd, stub.title, stub.company)
            if score >= args.threshold:
                eligible.append((stub, score, jd))
            if (i + 1) % 20 == 0:
                print(f"  detailed {i + 1}/{min(len(stubs), args.max_detail)} ...")

    if not eligible:
        print("\nNo jobs met the threshold. Try lowering --threshold or broadening --query.")
        return

    eligible.sort(key=lambda x: -x[1])
    total = len(eligible)
    per = max(1, args.per_page)
    num_output_pages = (total + per - 1) // per

    for p in range(num_output_pages):
        chunk = eligible[p * per : (p + 1) * per]
        print("\n" + "=" * 70)
        print(f"OUTPUT PAGE {p + 1}/{num_output_pages}  (eligible jobs {p * per + 1}-{p * per + len(chunk)} of {total})")
        print("=" * 70)
        for stub, score, jd in chunk:
            apply_link = f"{BASE}/viewjob?jk={stub.jk}"
            print(f"\n--- {stub.title} ---")
            print("Company:  ", stub.company or "(see page)")
            print("Location: ", stub.location or "(see page)")
            print("Match:    ", round(score, 4))
            print("Job URL:  ", apply_link)
            print("Apply:    ", apply_link)
            jd_preview = (jd[:1200] + "…") if len(jd) > 1200 else jd
            print("JD:\n", jd_preview or "(empty — page may require login or HTML changed)")

    print(f"\nDone. {total} eligible job(s), threshold={args.threshold}.")


if __name__ == "__main__":
    main()
