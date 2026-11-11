#!/bin/bash
# Lab 2 - Retire.js: scan the JavaScript libraries shipped inside the application
# (the Spring Boot jar embeds web assets such as Swagger UI via webjars).
# Writes reports/retire-report.json and reports/retire-report.txt.
# Exit code 13 = a HIGH or CRITICAL vulnerable library was found (the gate);
# lower severities are kept in the reports.
set -uo pipefail
WORKSPACE="${WORKSPACE:-$PWD}"
mkdir -p reports
rm -rf target/js-scan && mkdir -p target/js-scan
# Extract the JavaScript files of every library embedded in the fat jar
python3 - target/js-scan target/*.jar <<'PY'
import io, os, sys, zipfile
out, fat = sys.argv[1], zipfile.ZipFile(sys.argv[2])
for name in fat.namelist():
    if name.startswith("BOOT-INF/lib/") and name.endswith(".jar"):
        lib = zipfile.ZipFile(io.BytesIO(fat.read(name)))
        for entry in lib.namelist():
            if entry.endswith(".js"):
                dest = os.path.join(out, os.path.basename(name)[:-4], entry)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(lib.read(entry))
PY
echo "JavaScript files found in the application: $(find target/js-scan -name '*.js' | wc -l)"
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e npm_config_cache=/tmp/.npm \
  -v "$WORKSPACE":/src -w /src node:20-slim sh -c '
    npm install -g --prefix /tmp/npm retire@5 >/dev/null 2>&1 &&
    # Full report: every library and every finding
    /tmp/npm/bin/retire --path target/js-scan --outputformat json --outputpath reports/retire-report.json
    /tmp/npm/bin/retire --path target/js-scan --verbose > reports/retire-report.txt 2>&1
    true'
cat reports/retire-report.txt
# Gate: fail only on HIGH/CRITICAL vulnerable libraries
python3 - reports/retire-report.json <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
counts = {}
for f in data.get("data", []):
    for r in f.get("results", []):
        for v in r.get("vulnerabilities", []):
            counts[v.get("severity", "unknown")] = counts.get(v.get("severity", "unknown"), 0) + 1
print("Retire.js findings by severity:", counts or "none")
sys.exit(13 if counts.get("high", 0) + counts.get("critical", 0) else 0)
PY
