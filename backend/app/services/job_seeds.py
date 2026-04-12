from datetime import datetime, timedelta
from typing import Any


def seed_jobs() -> list[dict[str, Any]]:
    now = datetime.utcnow()
    rows = [
        ("linkedin", "li-1", "Senior Backend Engineer", "Nova Labs", "Bengaluru", "full-time", "remote", ["Python", "FastAPI", "PostgreSQL", "AWS", "Docker"], "Build high-scale APIs and lead code quality."),
        ("indeed", "in-2", "Full Stack Developer", "Orbit Commerce", "Remote", "full-time", "remote", ["React", "TypeScript", "Node.js", "SQL"], "E-commerce platform; React + Node."),
        ("naukri", "nk-3", "Data Analyst", "Finvertex", "Mumbai", "full-time", "hybrid", ["SQL", "Python", "Excel", "Tableau"], "Dashboards and stakeholder reporting."),
        ("glassdoor", "gd-4", "ML Engineer", "InsightAI", "Hyderabad", "full-time", "hybrid", ["Python", "PyTorch", "MLOps", "AWS"], "Model deployment and monitoring."),
        ("bayt", "by-5", "Software Engineer", "Gulf Tech", "Dubai", "full-time", "onsite", ["Java", "Spring", "Microservices"], "Enterprise integrations across GCC clients."),
        ("linkedin", "li-6", "DevOps Engineer", "CloudCraft", "Pune", "full-time", "hybrid", ["Kubernetes", "Terraform", "CI/CD", "AWS"], "Platform reliability and IaC."),
        ("indeed", "in-7", "Product Manager", "Helio SaaS", "Remote", "full-time", "remote", ["Agile", "SQL", "Analytics", "Roadmapping"], "B2B SaaS roadmap and discovery."),
        ("internshala", "is-8", "Intern - Frontend", "StartGrid", "Delhi", "internship", "hybrid", ["React", "CSS", "REST"], "UI components and design system."),
        ("naukri", "nk-9", "Java Developer", "BankCore", "Chennai", "full-time", "onsite", ["Java", "Spring Boot", "Kafka", "SQL"], "Payments and core banking."),
        ("linkedin", "li-10", "Security Engineer", "ShieldOps", "Remote", "full-time", "remote", ["Python", "AWS", "Threat modeling"], "Secure SDLC and cloud hardening."),
    ]
    out: list[dict[str, Any]] = []
    for i, (src, eid, title, company, loc, jt, rem, skills, desc) in enumerate(rows):
        out.append(
            {
                "source": src,
                "external_id": eid,
                "title": title,
                "company": company,
                "location": loc,
                "description": desc,
                "salary_range": None,
                "job_type": jt,
                "remote": rem,
                "skills": skills,
                "posted_at": now - timedelta(hours=i * 3 + 1),
                "apply_url": f"https://example.com/apply/{eid}",
            }
        )
    return out


def match_score_resume(job_skills: list[str], resume_json: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    sk = resume_json.get("skills") or {}
    cand = [s.lower() for s in (sk.get("technical") or []) + (sk.get("tools") or [])]
    blob = " ".join(cand + [resume_json.get("summary") or ""]).lower()
    matching = [s for s in job_skills if s.lower() in blob or any(s.lower() in c for c in cand)]
    missing = [s for s in job_skills if s.lower() not in blob]
    overlap = len(matching) / max(1, len(job_skills))
    recency = 1.0
    semantic = overlap
    exp_bonus = 0.05 if resume_json.get("experience") else 0.0
    combined = min(1.0, 0.6 * semantic + 0.25 * overlap + 0.15 * recency + exp_bonus)
    score = round(100 * combined, 1)
    return score, matching, missing[:8]
