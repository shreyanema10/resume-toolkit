import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

BASE_DIR = Path(__file__).parent
RESUME_DATA = BASE_DIR.parent / "resume_data.json"
COMPANY_RESUME_DIR = BASE_DIR.parent / "Company Resume"
PROMPTS_DIR = BASE_DIR / "prompts"
MODEL = "claude-sonnet-4-6"

PERSONAS = ["recruiter", "hiring_manager", "ai_detector"]


def render_resume_text(data: dict) -> str:
    lines = [
        data["name"],
        data["title"],
        data["contact"],
        "",
        "SUMMARY",
        data["summary"],
        "",
        "EXPERIENCE",
    ]
    for job in data["experience"]:
        lines.append(f"{job['company']} | {job['title']} | {job['start']} – {job['end']}")
        for b in job["bullets"]:
            lines.append(f"  • {b['bold']}{b['text']}")
        lines.append("")

    lines.append("SKILLS")
    for s in data["skills"]:
        lines.append(f"  {s['category']}: {s['content']}")
    lines.append("")

    edu = data["education"]
    lines += ["EDUCATION", f"{edu['school']} | {edu['dates']}", edu["degree"], ""]
    lines += ["LEADERSHIP & ACTIVITIES", data["leadership"]]
    return "\n".join(lines)


def load_resume(company: str | None) -> str:
    if company:
        folder = COMPANY_RESUME_DIR / company.replace(" ", "_")
        json_candidates = list(folder.glob("*.json")) if folder.exists() else []
        if json_candidates:
            data = json.loads(json_candidates[0].read_text())
            return render_resume_text(data)
        # fall back to base if no tailored JSON found
        print(f"[warn] No tailored JSON found for '{company}', using base resume.")

    data = json.loads(RESUME_DATA.read_text())
    return render_resume_text(data)


async def run_judge(client: anthropic.AsyncAnthropic, persona: str, resume_text: str) -> dict:
    system_prompt = (PROMPTS_DIR / f"{persona}.txt").read_text()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": f"<resume>\n{resume_text}\n</resume>"}],
    )
    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # strip markdown fences if model added them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())


def print_report(results: list[dict]) -> None:
    SCORE_LABELS = {1: "Poor", 2: "Weak", 3: "OK", 4: "Strong", 5: "Excellent"}
    PERSONA_LABELS = {
        "recruiter": "RECRUITER (10-sec scan)",
        "hiring_manager": "HIRING MANAGER (domain depth)",
        "ai_detector": "AI DETECTOR (human vs. generated)",
    }

    print("\n" + "=" * 60)
    print("  RESUME JUDGE REPORT")
    print("=" * 60)

    for result in results:
        persona = result["persona"]
        print(f"\n{'─' * 60}")
        print(f"  {PERSONA_LABELS.get(persona, persona.upper())}")
        print(f"{'─' * 60}")

        for dim, data in result["dimensions"].items():
            score = data["score"]
            label = SCORE_LABELS.get(score, str(score))
            print(f"\n  {dim.replace('_', ' ').title():<25} {score}/5  [{label}]")
            print(f"  {data['reasoning']}")
            if data.get("flagged_phrases"):
                print(f"  Flagged: {', '.join(repr(p) for p in data['flagged_phrases'])}")

        print(f"\n  Verdict : {result['verdict']}")
        print(f"  Top fixes:")
        for i, fix in enumerate(result["top_fixes"], 1):
            print(f"    {i}. {fix}")

    # overall average
    all_scores = [
        d["score"]
        for r in results
        for d in r["dimensions"].values()
    ]
    avg = sum(all_scores) / len(all_scores)
    print(f"\n{'=' * 60}")
    print(f"  OVERALL AVERAGE SCORE: {avg:.1f} / 5.0")
    print("=" * 60 + "\n")


async def main(company: str | None) -> None:
    resume_text = load_resume(company)
    label = f"tailored for '{company}'" if company else "base"
    print(f"\nRunning panel of 3 judges on {label} resume...")

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results = await asyncio.gather(
        *[run_judge(client, p, resume_text) for p in PERSONAS]
    )
    results_list = list(results)
    print_report(results_list)

    output_path = BASE_DIR / "judge_output.json"
    output_path.write_text(json.dumps(results_list, indent=2))
    print(f"[saved] Raw judge output → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Resume Judge")
    parser.add_argument("--company", type=str, default=None,
                        help="Company name to evaluate tailored version (e.g. 'Arize AI')")
    args = parser.parse_args()
    asyncio.run(main(args.company))
