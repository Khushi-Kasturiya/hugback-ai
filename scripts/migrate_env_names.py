"""Rename obsolete ELARA_* settings without printing values; dry-run by default."""
import argparse
import os
import re
import tempfile
from pathlib import Path

RENAMES = {"ELARA_"+name: "HUGBACK_"+name for name in (
    "MODEL", "VOICE_NAME", "AUTH_MODE",
)}

def migrate(path, *, apply=False):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing a symlink environment file")
    text = path.read_text()
    keys = set(re.findall(r"(?m)^\s*(?:export\s+)?([A-Z_][A-Z_0-9]*)\s*=", text))
    pairs = [(old, new) for old, new in RENAMES.items() if old in keys]
    if any(new in keys for _, new in pairs):
        raise ValueError("Both old and new names exist; resolve explicitly before migration")
    for old, new in pairs:
        text = re.sub(r"(?m)^(\s*(?:export\s+)?)"+old+r"(?=\s*=)", lambda m: m[1]+new, text)
    if apply and pairs:
        descriptor, temp = tempfile.mkstemp(prefix=".env-migrate-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w") as output:
                output.write(text); output.flush(); os.fsync(output.fileno())
            os.replace(temp, path)  # atomic replacement; mkstemp mode 0600
        finally:
            if os.path.exists(temp): os.unlink(temp)
    return pairs

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=Path(__file__).resolve().parents[1]/".env")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    pairs = migrate(args.file, apply=args.apply)
    for old, new in pairs: print(f"{old} -> {new}")
    print("Names updated; values preserved." if args.apply else "Dry run; no file changed.")

if __name__ == "__main__": main()
