import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi

REPO = "nvidia/Nemotron-Personas-Korea"
REV = "ada0f5b53a38bb5a30cce09358adde883c1ab63a"
root = Path(sys.argv[1])

remote = {
    s.rfilename: s.lfs.sha256 if s.lfs else None
    for s in HfApi().dataset_info(REPO, revision=REV, files_metadata=True).siblings
}

lines = [
    f"# repo: {REPO} (dataset)",
    f"# revision: {REV}",
    f"# generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
    "# columns: sha256  size_bytes  path  lfs_check",
]
mismatch = 0
files = sorted(p for p in root.rglob("*") if p.is_file() and ".cache" not in p.parts and p.name != "MANIFEST.txt")
for p in files:
    rel = p.relative_to(root).as_posix()
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    expected = remote.get(rel)
    check = "n/a" if expected is None else ("OK" if expected == digest else "MISMATCH")
    mismatch += check == "MISMATCH"
    lines.append(f"{digest}  {p.stat().st_size}  {rel}  {check}")

missing = sorted(set(remote) - {p.relative_to(root).as_posix() for p in files})
lines.append(f"# files: {len(files)}, lfs mismatches: {mismatch}, missing: {missing or 'none'}")
(root / "MANIFEST.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
