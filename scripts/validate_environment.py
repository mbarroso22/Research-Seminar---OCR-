from __future__ import annotations

import json
import platform
import shutil
import sys


def main() -> None:
    report = {
        "python": sys.version,
        "platform": platform.platform(),
        "git": shutil.which("git"),
        "nvidia_smi": shutil.which("nvidia-smi"),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

