from __future__ import annotations

import asyncio
import json
import time

from app.config import settings
from app.services.llm_client import chat_json, llm_key_diagnosis


async def main() -> None:
    print("diagnosis", json.dumps(llm_key_diagnosis()), flush=True)
    print(
        "cfg",
        settings.nvidia_model,
        "thinking=",
        settings.nvidia_thinking,
        "json_thinking=",
        settings.nvidia_json_thinking,
        "chat_effort=",
        settings.nvidia_reasoning_effort,
        "json_effort=",
        settings.nvidia_json_reasoning_effort,
        "timeout=",
        settings.nvidia_timeout,
        flush=True,
    )
    t0 = time.perf_counter()
    data = await chat_json(
        [
            {
                "role": "system",
                "content": (
                    "Return ONLY JSON with keys: contact,summary,experience,education,skills. "
                    "Align extracted resume facts into clean ATS sections."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "draft_resume_json": {
                            "contact": {
                                "name": "Ada Lovelace",
                                "email": "ada@example.com",
                                "phone": "",
                                "location": "London",
                            },
                            "summary": "",
                            "experience": [
                                {
                                    "title": "Analyst",
                                    "company": "Analytical Engine",
                                    "start_date": "1842",
                                    "end_date": "1843",
                                    "bullets": ["Designed early computing algorithms"],
                                }
                            ],
                            "education": [
                                {
                                    "institution": "Home study",
                                    "degree": "",
                                    "field": "Mathematics",
                                    "year": "",
                                }
                            ],
                            "skills": {"technical": ["Mathematics", "Logic"]},
                        },
                        "resume_text": (
                            "Ada Lovelace, London. Analyst at Analytical Engine 1842-1843. "
                            "Mathematics, Logic."
                        ),
                        "template_name": "ATS Professional",
                    }
                ),
            },
        ],
        temperature=0.2,
        max_tokens=2048,
    )
    elapsed = time.perf_counter() - t0
    print(f"elapsed_s {elapsed:.1f}", flush=True)
    print("keys", sorted(data.keys()), flush=True)
    print("name", (data.get("contact") or {}).get("name"), flush=True)
    print("summary_len", len(str(data.get("summary") or "")), flush=True)
    print("exp", len(data.get("experience") or []), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
