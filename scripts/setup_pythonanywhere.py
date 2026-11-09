"""Prepare a fresh PythonAnywhere deployment; run with Python 3.11 or newer."""

import json
import os
import re
import secrets
import subprocess
import sys
import venv
from pathlib import Path


def main():
    if sys.platform != "linux" or sys.version_info < (3, 11):
        raise SystemExit("Run this in a PythonAnywhere Bash console with Python 3.11 or newer.")
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-zA-Z0-9-]+\.pythonanywhere\.com", sys.argv[1]):
        raise SystemExit("Usage: python3.13 scripts/setup_pythonanywhere.py USERNAME.pythonanywhere.com")
    domain = sys.argv[1].lower()
    project = Path(__file__).resolve().parents[1]
    private = project / ".local"
    private.mkdir(mode=0o700, exist_ok=True)
    config_path = private / "hosting.json"
    if not config_path.exists():
        config = {
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
            "DJANGO_ALLOWED_HOSTS": domain,
            "REFIT_DATA_DIR": str(Path.home() / "refit-data"),
        }
        with open(config_path, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as handle:
            json.dump(config, handle)
    config_path.chmod(0o600)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("DJANGO_ALLOWED_HOSTS") != domain or config.get("DJANGO_DEBUG") != "0":
        raise SystemExit("Existing hosting configuration differs. Review .local/hosting.json before continuing.")
    if not config.get("DJANGO_SECRET_KEY") or not config.get("REFIT_DATA_DIR"):
        raise SystemExit("Existing hosting configuration is incomplete; do not replace a live secret.")
    Path(config["REFIT_DATA_DIR"]).mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(config)
    environment["PIP_NO_CACHE_DIR"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    virtualenv = project / ".venv"
    python = virtualenv / "bin" / "python"
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(virtualenv)

    def run(*arguments):
        subprocess.run([str(python), *arguments], cwd=project, env=environment, check=True)

    run("-m", "pip", "install", "--no-cache-dir", "-r", "requirements.lock")
    run("manage.py", "migrate", "--noinput")
    run("manage.py", "collectstatic", "--noinput")
    run("manage.py", "check", "--deploy", "--fail-level", "WARNING")
    wsgi = private / "pythonanywhere_wsgi.py"
    wsgi.write_text(
        "import json\nimport os\nimport sys\nfrom pathlib import Path\n\n"
        f"project = Path({str(project)!r})\n"
        "sys.path.insert(0, str(project))\n"
        "os.environ.update(json.loads((project / '.local' / 'hosting.json').read_text()))\n"
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'refit.settings'\n"
        "from django.core.wsgi import get_wsgi_application\n"
        "application = get_wsgi_application()\n",
        encoding="utf-8",
    )
    print("\nRefIt preparation passed. It is not live until the Web tab is configured.")
    print(f"Domain: {domain}")
    print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}")
    print(f"Source code / working directory: {project}")
    print(f"Virtualenv: {virtualenv}")
    print(f"Static mapping: /static/ -> {project / 'staticfiles'}")
    print("Do NOT create a media or refit-data static mapping; uploads are private.")
    print("Replace the Web tab's WSGI file contents with this line:")
    print(f"exec(compile(open({str(wsgi)!r}).read(), {str(wsgi)!r}, 'exec'))")
    print("Reload the web app, then test HTTPS, signup, login, and a small upload.")
    print("Free hosting requires monthly renewal and shares 512 MiB across code, dependencies, and data.")


if __name__ == "__main__":
    main()
