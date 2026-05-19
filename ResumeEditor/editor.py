import os
import json
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

BASE_DIR = Path(__file__).parent
RESUME_DATA = BASE_DIR.parent / "resume_data.json"
JUDGE_OUTPUT = BASE_DIR / "judge_output.json"
PROMPTS_DIR = BASE_DIR / "prompts"
MODEL = "claude-sonnet-4-6"


def load_inputs() -> tuple[dict, list[dict]]:
    if not JUDGE_OUTPUT.exists():
        print("[error] judge_output.json not found. Run judge.py first.")
        sys.exit(1)
    resume = json.loads(RESUME_DATA.read_text())
    judge_results = json.loads(JUDGE_OUTPUT.read_text())
    return resume, judge_results


def call_editor(resume: dict, judge_results: list[dict]) -> list[dict]:
    system_prompt = (PROMPTS_DIR / "editor.txt").read_text()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_content = (
        "=== JUDGE FEEDBACK ===\n"
        + json.dumps(judge_results, indent=2)
        + "\n\n=== CURRENT RESUME JSON ===\n"
        + json.dumps(resume, indent=2)
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)["proposed_edits"]
    except (json.JSONDecodeError, KeyError):
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())["proposed_edits"]


def apply_edit(data: dict, before: str, after: str) -> tuple[dict, bool]:
    found = [False]

    def replace_in_value(obj):
        if isinstance(obj, str):
            if before in obj:
                found[0] = True
                return obj.replace(before, after, 1)
            return obj
        elif isinstance(obj, dict):
            return {k: replace_in_value(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_in_value(item) for item in obj]
        return obj

    new_data = replace_in_value(data)
    return new_data, found[0]


def show_diff(edit: dict) -> None:
    print(f"\n{'─' * 60}")
    print(f"  Edit #{edit['id']}  [{edit['risk'].upper()} RISK]  →  {edit['section']}")
    print(f"  Fixes: {', '.join(edit['addresses'])}")
    print(f"  Why: {edit['reasoning']}")
    print(f"\n  BEFORE: {edit['before']}")
    print(f"  AFTER:  {edit['after']}")


def prompt_approval(edit: dict) -> bool:
    while True:
        choice = input("\n  Apply this edit? [y/n/q to quit]: ").strip().lower()
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        if choice in ("q", "quit"):
            print("\nExiting without further edits.")
            sys.exit(0)
        print("  Please enter y, n, or q.")


MONTHS = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
          7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}


def generate_files(company: str) -> None:
    generate_script = BASE_DIR.parent / "generate_resume.py"
    print(f"\nGenerating PDF + DOCX for '{company}'...")
    subprocess.run(
        [sys.executable, str(generate_script), company],
        check=True,
        cwd=BASE_DIR.parent,
    )


def generate_base_version() -> None:
    month = MONTHS[datetime.now().month]
    year = datetime.now().year

    base_folder = BASE_DIR.parent / "Company Resume" / "BaseResumeVersion"
    base_folder.mkdir(parents=True, exist_ok=True)

    existing = list(base_folder.glob(f"BaseResume_{month}_{year}_v*.pdf"))
    version = len(existing) + 1
    out_path = base_folder / f"BaseResume_{month}_{year}_v{version}.pdf"

    sys.path.insert(0, str(BASE_DIR.parent))
    import generate_resume as gr
    resume = json.loads(RESUME_DATA.read_text())
    print(f"\nGenerating base resume version...")
    gr.generate_pdf(resume, out_path)
    print(f"[saved] {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Resume Editor")
    parser.add_argument("--company", type=str, default=None,
                        help="Company name — generates PDF + DOCX in Company Resume/<name>/ after edits")
    args = parser.parse_args()

    print("\nLoading judge output and resume data...")
    resume, judge_results = load_inputs()

    print("Calling editor agent...")
    edits = call_editor(resume, judge_results)
    print(f"\n{len(edits)} edits proposed. Review each one:\n")

    approved_count = 0
    current_resume = resume

    for edit in edits:
        show_diff(edit)
        if prompt_approval(edit):
            updated, found = apply_edit(current_resume, edit["before"], edit["after"])
            if found:
                current_resume = updated
                approved_count += 1
                print("  ✓ Applied.")
            else:
                print("  [warn] Exact text not found in resume — skipped.")
        else:
            print("  Skipped.")

    if approved_count == 0:
        print("\nNo edits applied. Resume unchanged.")
        return

    RESUME_DATA.write_text(json.dumps(current_resume, indent=2) + "\n")
    print(f"\n[saved] {approved_count} edit(s) applied → {RESUME_DATA}")

    if args.company:
        generate_files(args.company)
    else:
        save = input("\nGenerate a base resume PDF snapshot? [y/n]: ").strip().lower()
        if save in ("y", "yes"):
            generate_base_version()

    rerun = input("\nRe-run judge to see score delta? [y/n]: ").strip().lower()
    if rerun in ("y", "yes"):
        print("\nRunning judge...\n")
        cmd = [sys.executable, str(BASE_DIR / "judge.py")]
        if args.company:
            cmd += ["--company", args.company]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
