#!/usr/bin/env python3
"""
CI version of weekly_digest.sh.
Uses the Anthropic SDK directly instead of the local Claude CLI.
Called by .github/workflows/weekly-digest.yml.
"""

import openai
import os
import subprocess
import sys
from datetime import date

TODAY = date.today().strftime("%Y-%m-%d")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path, default=""):
    try:
        with open(os.path.join(REPO, path)) as f:
            return f.read()
    except FileNotFoundError:
        return default


def main():
    git_log = subprocess.run(
        ["git", "log", "--oneline", "--since=7 days ago"],
        capture_output=True, text=True, cwd=REPO,
    ).stdout.strip() or "(no commits this week)"

    git_status = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True, cwd=REPO,
    ).stdout.strip()[:2000] or "(clean)"

    charter = read("agents/orchestrator/charter.md")
    playbook = read("playbooks/weekly-founder-review.md")
    template = read("templates/weekly-founder-digest.md")

    prompt = f"""You are the Orchestrator agent for the MV metroidvania toolchain business.

## Your Charter
{charter}

## Playbook
{playbook}

## Output Template
{template}

## This Week's Git Activity
Commits (last 7 days):
{git_log}

Uncommitted changes:
{git_status}

## Task
Today is {TODAY}. Compile the weekly founder digest using the template above.

Base it entirely on the git activity shown — do not invent items.
Suppress low-signal status updates. Surface only decisions the founder must make
and risks that changed this week. Write the output as clean markdown ready to be emailed.

End with:
- Recommendation:
- Risks:
- Confidence:
- Founder approval needed:
- Next actions:"""

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    digest = response.choices[0].message.content

    artifact = os.path.join(REPO, f"artifacts/weekly-digest-{TODAY}.md")
    os.makedirs(os.path.dirname(artifact), exist_ok=True)
    with open(artifact, "w") as f:
        f.write(digest)

    print(f"Saved to {artifact}", flush=True)

    subprocess.run(
        [
            sys.executable,
            os.path.join(REPO, "scripts/send_weekly_digest.py"),
            "--file", artifact,
        ],
        check=True,
        cwd=REPO,
    )


if __name__ == "__main__":
    main()
