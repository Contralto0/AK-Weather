"""Offline start check for the complete portable application, including WPF."""
from pathlib import Path
import ast
import json
import ssl
import subprocess
import sys
import zipfile


def main():
    app = Path(__file__).resolve().parent
    version = json.loads((app / "version.json").read_text(encoding="utf-8"))
    if not isinstance(version.get("version"), str) or not version["version"]:
        raise ValueError("Version fehlt")
    ast.parse((app / "updater.py").read_text(encoding="utf-8"))
    ast.parse((app / "dwd_mosmix.py").read_text(encoding="utf-8"))
    ast.parse((app / "dwd_warnings.py").read_text(encoding="utf-8"))
    ast.parse((app / "dwd_current.py").read_text(encoding="utf-8"))
    ast.parse((app / "dwd_poi.py").read_text(encoding="utf-8"))
    ast.parse((app / "dwd_radolan.py").read_text(encoding="utf-8"))
    ast.parse((app / "dwd_reports.py").read_text(encoding="utf-8"))
    ast.parse((app / "konrad3d.py").read_text(encoding="utf-8"))
    ssl.create_default_context()
    with zipfile.ZipFile(app.parent / "runtime" / "python313.zip") as standard_library:
        if standard_library.testzip() is not None:
            raise ValueError("Python-Standardbibliothek beschädigt")
    result = subprocess.run(
        [str(app / "WeatherShell.exe"), "--self-test"],
        cwd=app, timeout=20, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        if sys.stderr:
            print("Startprüfung fehlgeschlagen: " + str(error), file=sys.stderr)
        sys.exit(1)
