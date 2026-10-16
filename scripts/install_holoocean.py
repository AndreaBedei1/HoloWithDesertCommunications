"""Install the pinned client without changing another project's source tree."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PIN = "git+https://github.com/byu-holoocean/HoloOcean.git@49e70552dfd97273b7dfbe755fbe65d7738b24b7#subdirectory=client"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", type=Path, help="Existing HoloOcean 2.3.0 client directory")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="holoocean-client-") as temp:
        target = PIN
        if args.client:
            if not (args.client / "setup.py").is_file():
                parser.error("--client must point to the client directory containing setup.py")
            target = str(Path(temp) / "client")
            shutil.copytree(args.client, target, ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__", ".git", "tests"))
        return subprocess.call([sys.executable, "-m", "pip", "install", "--no-deps", target])


if __name__ == "__main__":
    raise SystemExit(main())
