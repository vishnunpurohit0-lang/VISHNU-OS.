#!/usr/bin/env python3
"""
Copy 'D:\\submittions os' into 'submissions/' in the repository and push to GitHub.
"""

import os
import shutil
import subprocess

REPO_DIR = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os"
SRC_DIR = r"D:\submittions os"
DEST_DIR = os.path.join(REPO_DIR, "submissions")


def run(cmd, cwd=REPO_DIR):
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr)
    return res.returncode


def main():
    print("=" * 60)
    print("Pushing submissions to existing GitHub repo")
    print("=" * 60)

    # 1. Ensure submissions directory exists
    os.makedirs(DEST_DIR, exist_ok=True)

    # 2. Copy files from D:\submittions os
    copied = []
    for item in os.listdir(SRC_DIR):
        s = os.path.join(SRC_DIR, item)
        d = os.path.join(DEST_DIR, item)
        if os.path.isfile(s):
            shutil.copy2(s, d)
            copied.append(item)
            print(f"Copied: {item} ({os.path.getsize(d):,} bytes)")

    print(f"\nTotal files copied: {len(copied)}")

    # 3. Update .gitignore to avoid committing large test raw/vdi files
    gitignore_path = os.path.join(REPO_DIR, ".gitignore")
    ignore_entries = "\n*.raw\n*.vdi\nvm_screen*.png\n"
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()
        if "*.raw" not in content:
            with open(gitignore_path, "a") as f:
                f.write(ignore_entries)
    else:
        with open(gitignore_path, "w") as f:
            f.write(ignore_entries)

    # 4. Git operations
    print("\n[Git] Staging files...")
    run(["git", "add", "submissions", ".gitignore"])

    print("\n[Git] Status:")
    run(["git", "status", "--short"])

    print("\n[Git] Committing...")
    code = run(["git", "commit", "-m", "Add OS course submissions and lab reports"])

    print("\n[Git] Pushing to origin main...")
    push_code = run(["git", "push", "origin", "main"])

    if push_code == 0:
        print("\nSUCCESS! Submissions pushed to GitHub repository.")
    else:
        print(f"\nPush exited with code {push_code}")


if __name__ == "__main__":
    main()
