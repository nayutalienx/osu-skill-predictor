#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve
import zipfile


REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "web_ui_bundle"
PACKAGE_DIR = ARTIFACTS_DIR / "osu-skill-predictor-web"
RUNTIME_DIR = PACKAGE_DIR / "runtime"
PYTHON_HOME = Path(sys.executable).resolve().parent
LAUNCHER_SOURCE = ARTIFACTS_DIR / ".launcher.py"
PYI_WORK_DIR = ARTIFACTS_DIR / ".pyi-work"
PYI_SPEC_DIR = ARTIFACTS_DIR / ".pyi-spec"
TOSU_RELEASE_ZIP = "https://github.com/tosuapp/tosu/releases/download/v4.22.1/tosu-windows-v4.22.1.zip"

RUNTIME_FILES = [
    "python.exe",
    "pythonw.exe",
    "python3.dll",
    "python310.dll",
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vccorlib140.dll",
    "vcomp140.dll",
    "vcamp140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcruntime140_threads.dll",
]

PIP_PACKAGES = [
    "requests==2.32.3",
    "pandas==2.2.3",
    "scikit-learn==1.6.1",
    "joblib==1.4.2",
    "numpy==1.24.3",
    "scipy==1.15.2",
    "pydantic==2.10.6",
    "fastapi==0.115.8",
    "uvicorn==0.35.0",
]


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, *, ignore_patterns: tuple[str, ...] = ()) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*ignore_patterns))


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def pip_packages_cached(site_packages: Path, packages: list[str]) -> bool:
    if not site_packages.exists():
        return False
    installed = {p.name.lower() for p in site_packages.iterdir() if p.is_dir()}
    for spec in packages:
        name = spec.split("==")[0].replace("-", "_").lower()
        if name in installed:
            continue
        aliases: tuple[str, ...] = ()
        if name == "scikit_learn":
            aliases = ("sklearn",)
        if any(a in installed for a in aliases):
            continue
        return False
    return True


def build_runtime(*, force_pip: bool = False) -> None:
    for name in RUNTIME_FILES:
        src = PYTHON_HOME / name
        if src.exists():
            copy_file(src, RUNTIME_DIR / name)

    copy_tree(PYTHON_HOME / "DLLs", RUNTIME_DIR / "DLLs")
    copy_tree(PYTHON_HOME / "tcl", RUNTIME_DIR / "tcl")
    copy_tree(
        PYTHON_HOME / "Lib",
        RUNTIME_DIR / "Lib",
        ignore_patterns=("site-packages", "__pycache__", "*.pyc", "*.pyo", "test", "tests", "idlelib"),
    )

    site_packages = RUNTIME_DIR / "Lib" / "site-packages"
    if force_pip or not pip_packages_cached(site_packages, PIP_PACKAGES):
        if site_packages.exists():
            shutil.rmtree(site_packages)
        site_packages.mkdir(parents=True)
        print("Installing pip packages into bundle...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(site_packages),
                *PIP_PACKAGES,
            ],
            cwd=str(REPO_ROOT),
            check=True,
        )
    else:
        print("Pip packages already cached, skipping install.")


def copy_project_payload() -> None:
    copy_tree(REPO_ROOT / "app", PACKAGE_DIR / "app", ignore_patterns=("__pycache__", "*.pyc", "*.pyo"))
    copy_tree(REPO_ROOT / "ui", PACKAGE_DIR / "ui", ignore_patterns=("__pycache__", "*.pyc", "*.pyo"))
    copy_tree(REPO_ROOT / "ml", PACKAGE_DIR / "ml", ignore_patterns=("__pycache__", "*.pyc", "*.pyo"))
    copy_tree(REPO_ROOT / "models", PACKAGE_DIR / "models")


def patch_tosu_env(tosu_dir: Path) -> None:
    env_path = tosu_dir / "tosu.env"
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    wanted = {
        "OPEN_DASHBOARD_ON_STARTUP": "false",
        "ENABLE_AUTOUPDATE": "false",
    }
    updated: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "=" not in line:
            updated.append(line)
            continue
        key, _, _value = line.partition("=")
        normalized_key = key.strip()
        if normalized_key in wanted:
            updated.append(f"{normalized_key}={wanted[normalized_key]}")
            seen.add(normalized_key)
        else:
            updated.append(line)
    for key, value in wanted.items():
        if key not in seen:
            updated.insert(0, f"{key}={value}")
    env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def bundle_tosu() -> None:
    tosu_dir = PACKAGE_DIR / "tosu"
    tosu_exe = tosu_dir / "tosu.exe"
    if tosu_exe.exists():
        print("tosu already bundled, skipping download.")
        patch_tosu_env(tosu_dir)
        return

    tosu_dir.mkdir(parents=True, exist_ok=True)
    print("Downloading tosu...")
    archive_path = ARTIFACTS_DIR / "tosu-windows.zip"
    urlretrieve(TOSU_RELEASE_ZIP, archive_path)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(tosu_dir)
    archive_path.unlink(missing_ok=True)
    patch_tosu_env(tosu_dir)


def write_runtime_files() -> None:
    (PACKAGE_DIR / "server_entry.py").write_text(
        "from __future__ import annotations\n"
        "import sys\n"
        "import traceback\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = Path(__file__).resolve().parent / 'server.log'\n"
        "\n"
        "def _log(msg: str) -> None:\n"
        "    try:\n"
        "        with LOG.open('a', encoding='utf-8') as f:\n"
        "            f.write(f'[{datetime.now(timezone.utc).isoformat()}] {msg}\\n')\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "class _LogWriter:\n"
        "    def write(self, text: str) -> int:\n"
        "        if text and text.strip():\n"
        "            _log(text.rstrip())\n"
        "        return len(text)\n"
        "    def flush(self) -> None:\n"
        "        pass\n"
        "    def isatty(self) -> bool:\n"
        "        return False\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    writer = _LogWriter()\n"
        "    sys.stdout = writer\n"
        "    sys.stderr = writer\n"
        "    _log('Starting server on 127.0.0.1:8765')\n"
        "    try:\n"
        "        import uvicorn\n"
        "        uvicorn.run('ui.app:app', host='127.0.0.1', port=8765, log_level='info')\n"
        "    except Exception:\n"
        "        _log(traceback.format_exc())\n",
        encoding="utf-8",
    )
    (PACKAGE_DIR / "launcher.py").write_text(
        "from __future__ import annotations\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "import traceback\n"
        "import urllib.request\n"
        "import webbrowser\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n"
        "\n"
        "BASE = Path(__file__).resolve().parent\n"
        "LOG = BASE / 'launcher.log'\n"
        "URL = 'http://127.0.0.1:8765/'\n"
        "HEALTH = 'http://127.0.0.1:8765/health'\n"
        "\n"
        "def _log(msg: str) -> None:\n"
        "    try:\n"
        "        with LOG.open('a', encoding='utf-8') as f:\n"
        "            f.write(f'[{datetime.now(timezone.utc).isoformat()}] {msg}\\n')\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "def server_ready() -> bool:\n"
        "    try:\n"
        "        with urllib.request.urlopen(HEALTH, timeout=1.5) as response:\n"
        "            return 200 <= getattr(response, 'status', 0) < 500\n"
        "    except Exception:\n"
        "        return False\n"
        "\n"
        "def main() -> None:\n"
        "    try:\n"
        "        if not server_ready():\n"
        "            _log('Server not ready, spawning server_entry.py')\n"
        "            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n"
        "            subprocess.Popen([\n"
        "                str(BASE / 'runtime' / 'pythonw.exe'),\n"
        "                str(BASE / 'server_entry.py'),\n"
        "            ], cwd=str(BASE), creationflags=creationflags)\n"
        "            for _ in range(24):\n"
        "                if server_ready():\n"
        "                    break\n"
        "                time.sleep(0.5)\n"
        "        if server_ready():\n"
        "            _log('Server ready, opening browser')\n"
        "            webbrowser.open(URL)\n"
        "        else:\n"
        "            _log('Server failed to start within 12 seconds')\n"
        "    except Exception as exc:\n"
        "        _log(f'Launcher failed: {exc}\\n{traceback.format_exc()}')\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (PACKAGE_DIR / "shutdown.bat").write_text(
        "@echo off\r\n"
        "echo Stopping osu-skill-predictor...\r\n"
        "taskkill /f /im pythonw.exe >nul 2>&1\r\n"
        "taskkill /f /im tosu.exe >nul 2>&1\r\n"
        "echo Done.\r\n"
        "pause\r\n",
        encoding="ascii",
    )
    (PACKAGE_DIR / "shutdown.py").write_text(
        "from __future__ import annotations\n"
        "import os\n"
        "import subprocess\n"
        "import urllib.request\n"
        "from pathlib import Path\n"
        "\n"
        "BASE = Path(__file__).resolve().parent\n"
        "API = 'http://127.0.0.1:8765/api/live/shutdown'\n"
        "\n"
        "try:\n"
        "    urllib.request.urlopen(urllib.request.Request(API, method='POST', data=b''), timeout=3)\n"
        "except Exception:\n"
        "    pass\n"
        "\n"
        "pythonw = BASE / 'runtime' / 'pythonw.exe'\n"
        "if pythonw.exists():\n"
        "    subprocess.run(['taskkill', '/f', '/im', 'pythonw.exe'], capture_output=True)\n"
        "\n"
        "tosu_exe = BASE / 'tosu' / 'tosu.exe'\n"
        "if tosu_exe.exists():\n"
        "    subprocess.run(['taskkill', '/f', '/im', 'tosu.exe'], capture_output=True)\n"
        "\n"
        "pid_file = Path(os.environ.get('APPDATA', '')) / 'osu-skill-predictor' / 'tosu-web.pid'\n"
        "if pid_file.exists():\n"
        "    pid_file.unlink(missing_ok=True)\n"
        "\n"
        "print('Shutdown complete.')\n",
        encoding="utf-8",
    )
    (PACKAGE_DIR / "README.txt").write_text(
        "Run osu-skill-predictor-web.exe.\r\n"
        "The launcher starts the local web service, starts bundled tosu if needed, then opens the browser UI.\r\n"
        "Double-click shutdown.py to close the application.\r\n",
        encoding="utf-8",
    )


def build_exe_launcher() -> None:
    LAUNCHER_SOURCE.write_text(
        "from __future__ import annotations\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "def main() -> None:\n"
        "    base = Path(sys.executable).resolve().parent\n"
        "    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n"
        "    subprocess.Popen([str(base / 'runtime' / 'pythonw.exe'), str(base / 'launcher.py')], cwd=str(base), creationflags=creationflags)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onefile",
            "--name",
            "osu-skill-predictor-web",
            "--distpath",
            str(PACKAGE_DIR),
            "--workpath",
            str(PYI_WORK_DIR),
            "--specpath",
            str(PYI_SPEC_DIR),
            str(LAUNCHER_SOURCE),
        ],
        cwd=str(REPO_ROOT),
        check=True,
    )


def cleanup_temp_files() -> None:
    if LAUNCHER_SOURCE.exists():
        LAUNCHER_SOURCE.unlink()
    safe_rmtree(PYI_WORK_DIR)
    safe_rmtree(PYI_SPEC_DIR)


def build() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--force-pip", action="store_true", help="Reinstall pip packages even if cached")
    parser.add_argument("--force-tosu", action="store_true", help="Re-download tosu even if bundled")
    args = parser.parse_args()

    subprocess.run(["taskkill", "/f", "/im", "pythonw.exe"], capture_output=True)
    subprocess.run(["taskkill", "/f", "/im", "tosu.exe"], capture_output=True)

    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    build_runtime(force_pip=args.force_pip)

    if args.force_tosu and (PACKAGE_DIR / "tosu" / "tosu.exe").exists():
        shutil.rmtree(PACKAGE_DIR / "tosu")

    copy_project_payload()
    bundle_tosu()
    write_runtime_files()
    build_exe_launcher()
    cleanup_temp_files()
    print(f"Web UI bundle created under: {PACKAGE_DIR}")


if __name__ == "__main__":
    build()
