"""Capture report evidence screenshots with headless Chromium (Playwright).

Usage: python capture_screenshots.py <evidence_dir> <screenshots_dir> [prometheus_url]
  evidence_dir    folder holding a build's archived reports/ (copied from Jenkins)
  screenshots_dir where PNG files are written

Text reports (pre-commit, Retire.js, Gauntlt, monitoring check, console log) are rendered
in a terminal style; HTML reports (Trivy, ZAP) are captured as-is; Prometheus pages are
captured live.
"""
import html
import pathlib
import sys

from playwright.sync_api import sync_playwright

evidence = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()
prom = sys.argv[3] if len(sys.argv) > 3 else "http://192.168.56.10:9090"
out.mkdir(parents=True, exist_ok=True)

TERMINAL = """<html><head><meta charset="utf-8"><style>
body{{margin:0;background:#1e1e1e;font-family:Consolas,'DejaVu Sans Mono',monospace}}
.bar{{background:#323233;color:#ccc;padding:8px 14px;font:13px Segoe UI,Arial}}
pre{{color:#d4d4d4;font-size:13px;line-height:1.35;padding:14px;margin:0;white-space:pre-wrap}}
.ok{{color:#4ec9b0}}.bad{{color:#f48771}}.warn{{color:#dcdcaa}}
</style></head><body><div class="bar">{title}</div><pre>{body}</pre></body></html>"""


def colorize(text):
    lines = []
    for line in html.escape(text).splitlines():
        if any(k in line for k in ("Passed", "passed", " up", "RESULT: OK", "none", "PASS:")):
            line = f'<span class="ok">{line}</span>'
        elif any(k in line for k in ("Failed", "failed", "FAIL", "firing", "CRITICAL", "high")):
            line = f'<span class="bad">{line}</span>'
        elif any(k in line for k in ("WARN", "medium", "pending")):
            line = f'<span class="warn">{line}</span>'
        lines.append(line)
    return "\n".join(lines)


def text_shot(page, src, title, name, max_lines=120):
    if not src.exists():
        print("skip (missing)", src)
        return
    text = src.read_text(encoding="utf-8", errors="replace").splitlines()
    text = "\n".join(text[:max_lines]) + ("\n..." if len(text) > max_lines else "")
    page.set_content(TERMINAL.format(title=html.escape(title), body=colorize(text)))
    page.screenshot(path=str(out / name), full_page=True)
    print("ok", name)


def html_shot(page, src, name, height=None):
    if not src.exists():
        print("skip (missing)", src)
        return
    page.goto(src.as_uri())
    page.wait_for_timeout(800)
    if height:
        page.screenshot(path=str(out / name), clip={"x": 0, "y": 0, "width": 1400, "height": height})
    else:
        page.screenshot(path=str(out / name), full_page=True)
    print("ok", name)


def url_shot(page, url, name, wait=2500):
    try:
        page.goto(url, timeout=20000)
        page.wait_for_timeout(wait)
        page.screenshot(path=str(out / name), full_page=True)
        print("ok", name)
    except Exception as e:  # noqa: BLE001 - evidence capture is best effort
        print("skip", name, e)


r = evidence / "reports"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    text_shot(page, r / "secrets-scan.txt", "Jenkins - Secrets Scan (pre-commit / HMRC hooks) - Lab 1", "03-secrets-scan.png")
    html_shot(page, r / "trivy-sca-report.html", "05-trivy-sca.png")
    text_shot(page, r / "trivy-sca-report.txt", "Trivy SCA - packaged application (jar)", "05b-trivy-sca-summary.png", 60)
    html_shot(page, r / "trivy-iac-report.html", "07-trivy-iac.png", 2200)
    text_shot(page, r / "retire-report.txt", "Jenkins - Retire.js scan of bundled JavaScript - Lab 2", "06-retire.png")
    html_shot(page, r / "trivy-image-report.html", "09-trivy-image.png", 2200)
    text_shot(page, r / "gauntlt-report.txt", "Jenkins - Security acceptance tests (Gauntlt) - Lab 3", "10-gauntlt.png", 200)
    html_shot(page, r / "zap" / "zap-baseline-report.html", "11-zap.png", 2600)
    text_shot(page, r / "monitoring-check.txt", "Jenkins - Continuous Monitoring Check (Prometheus)", "12b-monitoring-check.png")
    text_shot(page, evidence / "console-summary.txt", "Jenkins - build console (stage summary)", "01b-console-summary.png", 200)
    url_shot(page, f"{prom}/alerts", "12-prometheus-alerts.png")
    url_shot(page, f"{prom}/targets", "12c-prometheus-targets.png")
    browser.close()
