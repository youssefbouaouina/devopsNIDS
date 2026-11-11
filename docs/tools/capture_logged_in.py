"""Open a visible browser window where the user signs in to Jenkins, SonarQube and Grafana
themselves, then capture the evidence screenshots for the report.

Usage: python capture_logged_in.py <screenshots_dir> <profile_dir> <build_number>
The script never handles credentials: it waits until each site shows a signed-in page.
"""
import json
import pathlib
import sys
import time
import urllib.parse

from playwright.sync_api import sync_playwright

out = pathlib.Path(sys.argv[1]).resolve()
profile = sys.argv[2]
build = sys.argv[3]
out.mkdir(parents=True, exist_ok=True)

VM = "http://192.168.56.10"
JENKINS = f"{VM}:8080/job/student-management/"
SONAR = f"{VM}:9000/dashboard?id=tn.esprit%3Astudent-management"
explore = {"datasource": "Prometheus", "queries": [{"refId": "A", "expr":
           'sum by (status) (rate(http_server_requests_seconds_count{job="student-management"}[1m]))'}],
           "range": {"from": "now-1h", "to": "now"}}
GRAFANA = f"{VM}:3000/explore?orgId=1&left=" + urllib.parse.quote(json.dumps(explore))


def wait_signed_in(page, url, login_marker, name, timeout=900):
    page.goto(url)
    start = time.time()
    while login_marker in page.url:
        if time.time() - start > timeout:
            raise SystemExit(f"Timed out waiting for sign-in to {name}")
        print(f"Waiting for you to sign in to {name} in the browser window ...", flush=True)
        page.wait_for_timeout(5000)
        if login_marker not in page.url:
            break
        try:
            page.goto(url)
        except Exception:  # noqa: BLE001 - the user may be mid-navigation
            pass
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)
    print(f"Signed in to {name}", flush=True)


def shot(page, name):
    page.screenshot(path=str(out / name), full_page=True)
    print("ok", name, flush=True)


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(profile, headless=False,
                                               viewport={"width": 1500, "height": 950})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    wait_signed_in(page, JENKINS, "/login", "Jenkins")
    shot(page, "01-jenkins-stage-view.png")
    for path, name in ((f"{build}/", "02-jenkins-artifacts.png"),
                       (f"{build}/pipeline-graph/", "01c-jenkins-pipeline-graph.png"),
                       (f"{build}/pipeline-overview/", "01d-jenkins-pipeline-overview.png")):
        try:
            resp = page.goto(JENKINS + path)
            if resp and resp.ok:
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2500)
                shot(page, name)
        except Exception as e:  # noqa: BLE001
            print("skip", name, e, flush=True)

    wait_signed_in(page, SONAR, "/sessions/new", "SonarQube")
    page.wait_for_timeout(2500)
    shot(page, "08-sonarqube.png")

    wait_signed_in(page, GRAFANA, "/login", "Grafana")
    page.wait_for_timeout(5000)
    shot(page, "13-grafana.png")
    ctx.close()
print("DONE", flush=True)
