"""Exercise the setup script with isolated interpreter/uv command fixtures."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup-python.sh"


class PythonSetupTests(unittest.TestCase):
    def test_incompatible_environment_is_preserved_and_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            shutil.copy(SCRIPT, root / "scripts/setup-python.sh")
            commands = root / "commands"
            commands.mkdir()
            for name in ("dirname", "date", "mv"):
                (commands / name).symlink_to(shutil.which(name))
            # No compatible Python on PATH: force the uv provisioning branch.
            (commands / "python3").write_text("#!/bin/sh\nexit 1\n")
            (commands / "python3").chmod(0o755)
            uv = commands / "uv"
            uv.write_text(
                f"""#!{sys.executable}
import sys, subprocess
from pathlib import Path
args=sys.argv[1:]
with Path({str(root/'uv-calls')!r}).open('a') as f: f.write(' '.join(args)+'\\n')
if 'find' in args: print({sys.executable!r})
elif 'venv' in args: subprocess.run([{sys.executable!r},'-m','venv',args[-1]],check=True)
"""
            )
            uv.chmod(0o755)
            old = root / "backend/.venv"
            (old / "bin").mkdir(parents=True)
            (old / "bin/python").write_text("#!/bin/sh\nexit 1\n")
            (old / "bin/python").chmod(0o755)
            (old / "retained-file").write_text("preserve existing local contents")
            env = {**os.environ, "PATH": str(commands)}
            result = subprocess.run(
                ["/bin/bash", str(root / "scripts/setup-python.sh")],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            backups = list((root / "backend").glob(".venv-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(
                (backups[0] / "retained-file").read_text(),
                "preserve existing local contents",
            )
            self.assertEqual(
                subprocess.check_output(
                    [
                        str(old / "bin/python"),
                        "-c",
                        "import sys;print(sys.version_info.minor)",
                    ],
                    text=True,
                ).strip(),
                "12",
            )
            calls = (root / "uv-calls").read_text()
            self.assertIn("--native-tls python install 3.12", calls)
            self.assertIn("--managed-python 3.12", calls)
            # A second run must reuse the environment, without moving it again or invoking uv.
            again = subprocess.run(
                ["/bin/bash", str(root / "scripts/setup-python.sh")],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual((root / "uv-calls").read_text(), calls)
            self.assertEqual(len(list((root / "backend").glob(".venv-backup-*"))), 1)


if __name__ == "__main__":
    unittest.main()
