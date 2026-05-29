#!/usr/bin/env python3
"""
generate_secrets.py — Encrypt GITHUB_PAT into secrets.enc using double-Fernet.

Run this locally ONCE after getting your PAT:
    python generate_secrets.py

It will:
  1. Generate two Fernet keys (PRIMARY + FALLBACK) if not already in .env
  2. Prompt for your GITHUB_PAT
  3. Double-encrypt and write secrets.enc
  4. Print the two keys — save them as GitHub repo secrets:
       ENCRYPTION_KEY_PRIMARY
       ENCRYPTION_KEY_FALLBACK

secrets.enc is safe to commit. It is useless without both keys.
"""

import json
import os
import sys
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("ERROR: Run:  pip install cryptography")
    sys.exit(1)


ENV_FILE = Path(__file__).with_name(".env")
VAULT_FILE = Path(__file__).with_name("secrets.enc")


def _load_or_generate_keys() -> tuple[bytes, bytes]:
    primary_str = os.environ.get("ENCRYPTION_KEY_PRIMARY", "")
    fallback_str = os.environ.get("ENCRYPTION_KEY_FALLBACK", "")

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"')
            if k == "ENCRYPTION_KEY_PRIMARY" and not primary_str:
                primary_str = v
            if k == "ENCRYPTION_KEY_FALLBACK" and not fallback_str:
                fallback_str = v

    generated = []
    if not primary_str:
        primary_str = Fernet.generate_key().decode()
        generated.append(("ENCRYPTION_KEY_PRIMARY", primary_str))
    if not fallback_str:
        fallback_str = Fernet.generate_key().decode()
        generated.append(("ENCRYPTION_KEY_FALLBACK", fallback_str))

    if generated:
        with open(ENV_FILE, "a", encoding="utf-8") as f:
            for k, v in generated:
                f.write(f"{k}={v}\n")
        print(f"[generate_secrets] New keys written to {ENV_FILE}")

    return primary_str.encode(), fallback_str.encode()


def _double_encrypt(plaintext: str, primary: bytes, fallback: bytes) -> str:
    inner = Fernet(fallback).encrypt(plaintext.encode())
    outer = Fernet(primary).encrypt(inner)
    return outer.decode()


def main():
    print("=== RepoSwitchAuto — Secret Generator ===\n")

    primary, fallback = _load_or_generate_keys()

    existing: dict = {}
    if VAULT_FILE.exists():
        with open(VAULT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Existing secrets.enc found with keys: {list(existing.keys())}")

    print("\nEnter your GitHub Personal Access Token (classic, repo scope).")
    print("Leave blank to skip and keep existing value.\n")

    pat = input("GITHUB_PAT: ").strip()
    if not pat and "GITHUB_PAT" in existing:
        print("Keeping existing GITHUB_PAT.")
    elif pat:
        existing["GITHUB_PAT"] = _double_encrypt(pat, primary, fallback)
        print("GITHUB_PAT encrypted.")
    else:
        print("ERROR: GITHUB_PAT is required.")
        sys.exit(1)

    with open(VAULT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    print(f"\n[OK] secrets.enc written to {VAULT_FILE}")
    print("\n" + "="*60)
    print("IMPORTANT — Add these as GitHub repo secrets in RepoSwitchAuto:")
    print("="*60)
    print(f"  ENCRYPTION_KEY_PRIMARY  = {primary.decode()}")
    print(f"  ENCRYPTION_KEY_FALLBACK = {fallback.decode()}")
    print("="*60)
    print("\nDO NOT commit .env — it is in .gitignore.")
    print("secrets.enc is safe to commit (encrypted).\n")


if __name__ == "__main__":
    main()
