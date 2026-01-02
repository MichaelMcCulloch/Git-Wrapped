import os
import subprocess
import json
from collections import defaultdict
from datetime import datetime

# --- CONFIGURATION ---
ROOT_DIR = os.path.expanduser("~/Development")
OUTPUT_FILE = "repo_aware_history.json"

# Update with your identities
MY_EMAILS = {
    "your email",
}
MY_NAMES = {
    "your name",
}

# Map extensions to languages
EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".rs": "Rust",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".c": "C",
    ".h": "C",
    ".hpp": "C++",
    ".cpp": "C++",
    ".cc": "C++",
    ".cu": "CUDA",
    ".cuh": "CUDA",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".md": "Markdown",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".sql": "SQL",
    ".dockerfile": "Docker",
    "dockerfile": "Docker",
    ".xml": "XML",
    ".vue": "Vue",
    ".jsx": "React",
    ".tsx": "React",
    ".toml": "TOML",
    ".lua": "Lua",
}


def get_git_repos(root):
    print(f"📂 Scanning {root} for repositories...")
    git_repos = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            git_repos.append(dirpath)
            dirnames[:] = []
            continue
        # Skip dependency heavy folders
        for skip in [
            ".git",
            "node_modules",
            "venv",
            "target",
            "dist",
            "build",
            "vendor",
            "deps",
            "__pycache__",
        ]:
            if skip in dirnames:
                dirnames.remove(skip)
    return git_repos


# --- ADD THIS TO YOUR CONFIGURATION SECTION ---
# Files that represent "Data" or "Dependencies", not "Code"
IGNORE_EXTENSIONS = {
    ".lock",  # Dependency locks
    ".svg",  # Vector graphics (often massive XMLs)
    ".map",  # JS Source maps
    ".csv",  # Data files
    ".tsv",  # Data files
    ".min.js",  # Minified code
    ".min.css",  # Minified styles
    ".jsonl",  # Large data dumps
    ".ipynb",  # Jupyter Notebooks (often contain massive base64 blobs/output)
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".webp",  # Binaries that might slip through
}

IGNORE_EXACT_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "composer.lock",
    "Cargo.lock",
    "Gemfile.lock",
    "poetry.lock",
}


# --- REPLACE YOUR EXISTING parse_git_log FUNCTION WITH THIS ---
def parse_git_log(repo_path):
    """
    Parses git log with --numstat.
    UPDATED: Now filters out lockfiles, assets, and data files.
    """
    commits = []

    # Format: HASH | ISO_DATE | AUTHOR | EMAIL
    cmd = [
        "git",
        "-C",
        repo_path,
        "log",
        "--all",
        "--no-merges",
        "--format=HEADER|%H|%aI|%an|%ae",
        "--numstat",
    ]

    try:
        # errors='replace' handles non-utf8 characters
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        current_commit = None

        for line in result.stdout.splitlines():
            if line.startswith("HEADER|"):
                # Save previous commit
                if current_commit:
                    if is_me(current_commit["name"], current_commit["email"]):
                        commits.append(current_commit)

                parts = line.split("|")
                current_commit = {
                    "hash": parts[1],
                    "date": parts[2],
                    "name": parts[3].strip(),
                    "email": parts[4].strip().lower(),
                    "additions": 0,
                    "deletions": 0,
                    "files": 0,
                }
            elif current_commit and line.strip():
                # Parse numstat: "10  5   src/main.py"
                try:
                    # distinct split to handle filenames with spaces correctly
                    parts = line.split(maxsplit=2)
                    if len(parts) >= 3:
                        added = parts[0]
                        deleted = parts[1]
                        filename = parts[2].strip()

                        # --- NEW FILTERING LOGIC ---
                        # 1. Check exact filenames (like package-lock.json)
                        if os.path.basename(filename) in IGNORE_EXACT_FILES:
                            continue

                        # 2. Check extensions (like .csv, .map)
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in IGNORE_EXTENSIONS:
                            continue
                        # ---------------------------

                        if added != "-":
                            current_commit["additions"] += int(added)
                        if deleted != "-":
                            current_commit["deletions"] += int(deleted)
                        current_commit["files"] += 1
                except ValueError:
                    pass

        # Append last commit
        if current_commit and is_me(current_commit["name"], current_commit["email"]):
            commits.append(current_commit)

    except Exception as e:
        print(f"Error parsing log for {repo_path}: {e}")

    return commits


def is_me(name, email):
    if email in MY_EMAILS or name in MY_NAMES:
        return True
    for my_id in MY_EMAILS:
        if my_id in email:
            return True
    return False


def get_current_languages(repo_path):
    languages = defaultdict(int)
    cmd_files = ["git", "-C", repo_path, "ls-files"]
    try:
        res = subprocess.run(
            cmd_files, capture_output=True, text=True, errors="replace"
        )
        for file in res.stdout.splitlines():
            ext = os.path.splitext(file)[1].lower()
            if ext in EXTENSIONS:
                languages[EXTENSIONS[ext]] += 1
    except:
        pass
    return languages


def estimate_hours(commits):
    """
    Heuristic: Sort all commits by time.
    If diff < 2 hours, add diff. If diff > 2 hours, add 1 hour (start of session).
    """
    if not commits:
        return 0

    # Sort by date
    dates = sorted([datetime.fromisoformat(c["date"]) for c in commits])

    total_seconds = 0
    # Initial session assumption (1 hour for the first commit)
    total_seconds += 3600

    for i in range(1, len(dates)):
        diff = (dates[i] - dates[i - 1]).total_seconds()
        if diff < 7200:  # 2 hours
            total_seconds += diff
        else:
            total_seconds += 3600  # Start new session assumption

    return total_seconds / 3600


def main():
    repos = get_git_repos(ROOT_DIR)
    print(f"✅ Found {len(repos)} repositories.")

    all_commits = []
    language_counts = defaultdict(int)
    repo_totals = {}

    print("🚀 Mining commit history for Impact & Churn...")

    for repo_path in repos:
        repo_name = os.path.basename(repo_path)
        print(f"   Analyzing {repo_name}...")

        # 1. Get History (Time & Impact)
        repo_commits = parse_git_log(repo_path)

        for c in repo_commits:
            # Flatten for easier pandas processing later
            flat_commit = {
                "date": c["date"],
                "repo": repo_name,
                "additions": c["additions"],
                "deletions": c["deletions"],
                "impact": c["additions"] + c["deletions"],
            }
            all_commits.append(flat_commit)

        # 2. Get Snapshot (Languages)
        repo_langs = get_current_languages(repo_path)
        for lang, count in repo_langs.items():
            language_counts[lang] += count

        if len(repo_commits) > 0:
            repo_totals[repo_name] = len(repo_commits)

    # Calculate Global Stats
    total_hours = estimate_hours(all_commits)

    print("\n✨ Analysis Complete!")
    print(f"   - {len(all_commits)} linked commits")
    print(f"   - {int(total_hours)} estimated hours of coding")

    export_data = {
        "detailed_commits": all_commits,
        "languages": language_counts,
        "repos": repo_totals,
        "total_hours_estimated": total_hours,
        "generated_at": datetime.now().isoformat(),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(export_data, f, indent=2)
    print(f"💾 Saved deep-data to '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()
