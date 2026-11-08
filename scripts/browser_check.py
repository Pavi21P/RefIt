"""Isolated Chromium smoke check. Uses a temporary database and media directory."""

import base64
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / ".local" / "qa"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
CHROME = os.environ.get("REFIT_CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def run():
    with tempfile.TemporaryDirectory(prefix="refit-browser-") as temp:
        env = {**os.environ, "REFIT_DATA_DIR": temp, "DJANGO_DEBUG": "1"}
        subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput"],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        with open(ARTIFACTS / "server.log", "w") as log:
            server = subprocess.Popen(
                [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(base, timeout=2).close()
                        break
                    except OSError:
                        if server.poll() is not None:
                            raise RuntimeError("Test server stopped unexpectedly")
                        time.sleep(0.1)
                with sync_playwright() as pw:
                    options = {"executable_path": CHROME} if Path(CHROME).exists() else {}
                    browser = pw.chromium.launch(headless=True, **options)
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 1000}, color_scheme="light"
                    )
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base)
                    expect(page.get_by_role("heading", name="Keep what catches your eye.")).to_be_visible()
                    page.locator(".masonry img").first.wait_for(state="visible")
                    page.screenshot(path=str(ARTIFACTS / "01-gallery-light.png"), full_page=True)
                    page.get_by_role("link", name="Start your library").click()
                    page.get_by_label("Username:", exact=True).fill("browser-artist")
                    page.get_by_label("Password:", exact=True).fill("Local-test-only-729-Morning")
                    page.get_by_label("Password confirmation:", exact=True).fill(
                        "Local-test-only-729-Morning"
                    )
                    page.get_by_role("button", name="Create account").click()
                    expect(page.get_by_role("heading", name="All references")).to_be_visible()
                    page.get_by_role("button", name="Create folder", exact=True).click()
                    page.get_by_label("Folder name", exact=True).fill("Light studies")
                    page.get_by_role("button", name="Create folder", exact=True).last.click()
                    expect(page.get_by_role("heading", name="Light studies")).to_be_visible()
                    page.get_by_role("button", name="Add images", exact=True).click()
                    page.locator("#image-files").set_input_files(
                        [str(ROOT / "static/studies/28560.jpg"), str(ROOT / "static/studies/80607.jpg")]
                    )
                    page.locator("#upload-tags").fill("#warm-light #painting")
                    page.get_by_role("button", name="Add to library", exact=True).click()
                    expect(page.locator("#upload-dialog")).not_to_be_visible(timeout=20000)
                    expect(page.locator(".reference-card")).to_have_count(2)
                    page.get_by_label("Search references or #tags").fill("#warm-light")
                    page.get_by_role("button", name="Search", exact=True).click()
                    expect(page.locator(".reference-card")).to_have_count(2)
                    page.get_by_role("link", name="Clear filters", exact=True).click()
                    page.get_by_role("link", name="28560", exact=True).first.click()
                    page.get_by_label("Title:", exact=True).fill("Afternoon room")
                    page.get_by_label("Notes:", exact=True).fill(
                        "Look at the blue shadows against the ochre floor."
                    )
                    page.get_by_label("Tags:", exact=True).fill("#interiors #warm-light")
                    page.get_by_role("button", name="Save changes").click()
                    expect(page.get_by_role("heading", name="Afternoon room")).to_be_visible()
                    with page.expect_download() as download:
                        page.get_by_role("link", name="Download original").click()
                    assert download.value.suggested_filename == "Afternoon room.jpg"
                    page.get_by_role("button", name="Move to Trash").click()
                    page.locator(".trash-link").click()
                    page.get_by_role("link", name="Afternoon room", exact=True).first.click()
                    page.get_by_role("button", name="Restore reference").click()
                    page.get_by_role("link", name="Back to library").click()
                    expect(page.locator(".reference-card")).to_have_count(2)
                    page.get_by_role("button", name="Favorite Afternoon room", exact=True).click()
                    expect(
                        page.get_by_role("button", name="Remove Afternoon room from favorites")
                    ).to_be_visible()
                    # Exercise the paste and drop event paths with image files; this does not alter the OS clipboard.
                    stream = io.BytesIO()
                    Image.new("RGB", (220, 300), "#647556").save(stream, "PNG")
                    encoded = base64.b64encode(stream.getvalue()).decode()
                    for event_type, filename in [
                        ("paste", "Pasted study.png"),
                        ("drop", "Dropped study.png"),
                    ]:
                        page.evaluate(
                            """({encoded, eventType, filename}) => {
                            const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
                            const transfer = new DataTransfer(); transfer.items.add(new File([bytes], filename, {type:'image/png'}));
                            const event = eventType === 'paste' ? new ClipboardEvent('paste', {clipboardData:transfer, bubbles:true, cancelable:true}) : new DragEvent('drop', {dataTransfer:transfer, bubbles:true, cancelable:true});
                            document.dispatchEvent(event);
                        }""",
                            {"encoded": encoded, "eventType": event_type, "filename": filename},
                        )
                        expect(page.locator("#upload-dialog")).to_be_visible()
                        page.get_by_role("button", name="Add to library", exact=True).click()
                        expect(page.locator("#upload-dialog")).not_to_be_visible(timeout=20000)
                    expect(page.locator(".reference-card")).to_have_count(4)
                    columns = page.locator(".reference-card").evaluate_all(
                        "cards => new Set(cards.map(card => Math.round(card.getBoundingClientRect().left))).size"
                    )
                    assert columns == 3, f"Expected three filled desktop columns, got {columns}"
                    page.get_by_role("button", name="Switch to dark mode").click()
                    page.reload()
                    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
                    page.screenshot(path=str(ARTIFACTS / "02-library-dark.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        "Horizontal overflow on mobile"
                    )
                    page.get_by_role("button", name="Toggle collections").click()
                    expect(page.locator("#sidebar")).to_be_visible()
                    page.get_by_role("button", name="Toggle collections").click()
                    expect(page.locator("#sidebar")).not_to_be_visible()
                    page.get_by_role("button", name="Switch to light mode").click()
                    page.screenshot(path=str(ARTIFACTS / "03-library-mobile.png"), full_page=True)
                    page.get_by_label("Account menu").click()
                    page.get_by_role("button", name="Log out").click()
                    page.get_by_role("link", name="Log in", exact=True).first.click()
                    page.get_by_label("Username:", exact=True).fill("browser-artist")
                    page.get_by_label("Password:", exact=True).fill("Local-test-only-729-Morning")
                    page.get_by_role("button", name="Log in", exact=True).click()
                    expect(page.locator(".reference-card")).to_have_count(4)
                    assert not errors, errors
                    browser.close()
                print(
                    json.dumps(
                        {
                            "result": "passed",
                            "checks": [
                                "signup",
                                "folder creation",
                                "multi-file upload",
                                "tag search",
                                "image edit",
                                "download",
                                "trash and restore",
                                "favorites",
                                "paste event",
                                "drop event",
                                "theme persistence",
                                "mobile overflow and menu",
                                "logout/login persistence",
                            ],
                            "screenshots": str(ARTIFACTS),
                            "javascript_errors": errors,
                        },
                        indent=2,
                    )
                )
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == "__main__":
    run()
