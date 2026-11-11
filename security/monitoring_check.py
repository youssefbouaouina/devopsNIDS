"""Phase 4 (Operations): summarise Prometheus scrape health, security alert rules and alerts.

Usage: python3 security/monitoring_check.py http://localhost:9090
Exit code 1 if the application is not scraped or the security rules are not loaded.
"""
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")


def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.load(r)["data"]


ok = True
print("=== Prometheus scrape targets ===")
for t in get("/api/v1/targets?state=active")["activeTargets"]:
    job, health = t["labels"].get("job"), t["health"]
    print(f"  {job:<22} {health}")
    if job == "student-management" and health != "up":
        ok = False

print("=== Security alert rules ===")
rules = [r for g in get("/api/v1/rules")["groups"] for r in g["rules"]]
for r in rules:
    print(f"  {r['name']:<28} state={r.get('state', '-')}")
if not any(r["name"] == "StudentAppDown" for r in rules):
    ok = False

print("=== Active alerts ===")
alerts = get("/api/v1/alerts")["alerts"]
for a in alerts:
    print(f"  {a['labels']['alertname']:<28} {a['state']}  {a['annotations'].get('summary', '')}")
if not alerts:
    print("  none")

print("RESULT:", "OK" if ok else "PROBLEM")
sys.exit(0 if ok else 1)
