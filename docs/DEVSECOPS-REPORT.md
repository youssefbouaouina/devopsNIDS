# DevSecOps Project Report: student-management

**Module:** Labs: Cybersecurity and Coding (5NIDS6), Esprit
**Supervisor:** Nawel Hammami
**Team:** Youssef Bouaouina, *(partner name)*
**Validation:** Thursday 12/11/2026
**Repository:** https://github.com/youssefbouaouina/devopsNIDS (branch `devsecops/lab1-pre-commit`)

---

## 1. Objective

Start from the CI/CD pipeline built in the 4th-year DevOps module and turn it into a full
**DevSecOps** pipeline, adding security to each phase of the software lifecycle
(Development, Acceptance, Production, Operations). Following the course's advice ("Do less, but
do it better"), we picked one well-integrated tool or practice per security activity
instead of many shallow ones. Every tool runs automatically in Jenkins, and every report is
kept as a build artifact.

## 2. Starting point: the DevOps pipeline (4th year)

```
GitHub ─▶ Jenkins ─▶ Maven ─▶ SonarQube ─▶ Docker Hub ─▶ Kubernetes (Minikube) ─▶ Prometheus/Grafana
```

| Component | Role |
|---|---|
| Spring Boot 3 / Maven app (`student-management`) | REST API + MySQL |
| Jenkins (VM, Vagrant) | CI/CD orchestration (`Jenkinsfile`) |
| SonarQube | Code quality |
| Docker / Docker Hub | Image build and registry |
| Minikube | Deployment (namespace `devops`, MySQL + Spring app) |
| Prometheus + Grafana | Metrics and dashboards |

Everything runs in a single Ubuntu VM described as code (`infra/vagrant`).

## 3. Target DevSecOps pipeline

```
 DEVELOPMENT                                  ACCEPTANCE        PRODUCTION       OPERATIONS
 ┌──────────────┐ ┌───────┐ ┌──────────┐ ┌───────┐ ┌───────┐ ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
 │Secrets scan  │▶│ Build │▶│SCA + IaC │▶│ SAST  │▶│Image  │▶│Push +│▶│Gauntlt │▶│ OWASP ZAP│▶│ Prometheus   │
 │(pre-commit)  │ │(Maven)│ │ (Trivy)  │ │(Sonar │ │scan   │ │Deploy│ │attacks │ │ baseline │ │ alerts check │
 │   Lab 1      │ │       │ │Lab 2 eq. │ │ gate) │ │(Trivy)│ │ (K8s)│ │ Lab 3  │ │          │ │              │
 └──────────────┘ └───────┘ └──────────┘ └───────┘ └───────┘ └──────┘ └────────┘ └──────────┘ └──────────────┘
         every stage writes to reports/  ──▶  archived by Jenkins with each build
```

| Phase | Security activity (course) | Tool chosen | Jenkins stage | Gate |
|---|---|---|---|---|
| Development (pre-commit) | Pre-commit security hooks | HMRC `security-git-hooks` via `pre-commit` | Secrets Scan (pre-commit) | Fails build |
| Development (commit) | Security Components Analysis | Trivy (`rootfs` on the jar) | SCA + IaC Scan (Trivy) | CRITICAL → UNSTABLE |
| Development (commit) | Infrastructure as Code analysis | Trivy (`config`) | SCA + IaC Scan (Trivy) | Report |
| Development (commit) | Static code analysis (SAST) | SonarQube + Quality Gate | SonarQube Analysis (SAST) | Fails build |
| Development (commit) | Container security | Trivy (`image`) | Container Scan (Trivy) | CRITICAL → UNSTABLE |
| Acceptance | Security acceptance testing | Gauntlt (nmap + curl adapters) | Security Acceptance Tests (Gauntlt) | Failure → UNSTABLE |
| Production | Security smoke tests | OWASP ZAP Baseline Scan | Security Smoke Test (OWASP ZAP) | FAIL alerts → UNSTABLE |
| Production | Secrets management | Jenkins Credentials + Kubernetes Secret | Push / Deploy | n/a |
| Operations | Continuous monitoring | Prometheus alert rules + Grafana | Continuous Monitoring Check | Report |

---

## 4. Phase 1: Development

### 4.1 Pre-commit security hooks (Lab 1)

**Goal:** stop secrets (keys, passwords, tokens, key files) from ever reaching the repository.

**Tool:** the `pre-commit` framework with HMRC `security-git-hooks` (release 1.15.0):
- `secrets_filecontent`: flags sensitive strings (AWS keys, certificates, application secrets…)
- `secrets_filename`: flags sensitive file types (`*.pem`, `*.key`, …)
- `hooks_version_check`: checks the hooks are up to date

**Configuration:** `.pre-commit-config.yaml` at the repository root (plus `repository.yaml`, required
by the HMRC hooks). Lab evidence (`lab1-evidence/`) and course material are excluded, because they
deliberately contain the fake AWS key used for the test.

**Integration:**
1. *Developer side:* `pipx install pre-commit && pre-commit install`. Every `git commit` runs the hooks.
2. *Pipeline side:* the **first** Jenkins stage runs `pre-commit run --all-files` in a `python:3.12`
   container, so the rule applies even to commits made without the local hook.

**Test (as in the lab):** `touch fake.key.pem` and
`echo aws_secret_access_key = 1ye+Vark… > fake.aws.file`, then `git commit`. Both hooks
**Failed** and the commit was refused. The same files planted in the Jenkins workspace make the
stage exit with code 1. On the real code base all hooks **Passed**.

![Commit blocked by pre-commit hooks](../lab1-evidence/cap1.PNG)
![pre-commit run --all-files](../lab1-evidence/cap2.PNG)
![Secrets Scan stage in Jenkins](screenshots/04-stage-secrets-scan.png)

### 4.2 Security Components Analysis (SCA): equivalent of Lab 2 (Retire.js)

**Why not Retire.js:** Retire.js only analyses JavaScript libraries. Our application is Java/Maven,
so we applied the same practice (find known-vulnerable third-party components and break the
build) with a tool that understands Java artifacts. The course slide on SCA lists OWASP
Dependency-Check for Java. We chose **Trivy**: it reads every library packaged inside the Spring
Boot fat jar, uses an up-to-date CVE database, and the same tool also covers IaC and container
scanning (one tool, three practices).

**Configuration:** `security/trivy.sh` runs Trivy 0.65.0 in a container with a persistent DB cache.
The stage produces `trivy-sca-report.html/.txt`. A second run with
`--severity CRITICAL --exit-code 1` marks the build **UNSTABLE** if a CRITICAL CVE is present.

**Results and remediation:**

| | Total CVEs in jar | CRITICAL | HIGH |
|---|---|---|---|
| Before (Spring Boot 3.5.5) | 71 | 9 | 26 |
| After upgrading to Spring Boot 3.5.15 | 22 | 7 | 6 |
| After pinning patched Tomcat 10.1.59, Jackson 2.21.7, commons-lang3 3.18.0, log4j 2.25.5 | 5 → **0 unaccepted** | 0 | 0 |

Remaining: two `spring-webmvc` CVEs (CVE-2026-47884, CVE-2026-47890) about **Server-Sent Events**.
They are only fixed in Spring Framework 7 (a Spring Boot 4 major upgrade). The application has no
SSE endpoint (checked in the source), so the vulnerable code is unreachable. They are documented as
**accepted risks** in `.trivyignore`, with a justification and an expiry date (2027-01-31).

![SCA report before](screenshots/05-trivy-sca-before.png)
![SCA report after](screenshots/06-trivy-sca-after.png)

### 4.3 Infrastructure as Code analysis

**Tool:** Trivy `config` (misconfiguration checks for Dockerfile and Kubernetes).

| File | Before | After |
|---|---|---|
| `Dockerfile` | 2 (1 HIGH: runs as root) | 1 LOW (no HEALTHCHECK; Kubernetes probes cover it) |
| `k8s/spring-app.yaml` | 18 (3 HIGH) | 2 MEDIUM |
| `k8s/mysql.yaml` | 16 (3 HIGH) | 16, accepted for the lab (the official MySQL image needs root at start-up) |

**Remediation applied:**
- `Dockerfile`: `eclipse-temurin:17-jre` instead of the JDK (smaller attack surface); dedicated user
  `app` (uid 10001); `USER 10001`.
- `k8s/spring-app.yaml`: `runAsNonRoot`, `runAsUser/Group 10001`, `seccompProfile: RuntimeDefault`,
  `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` (with an `emptyDir` for `/tmp`),
  `capabilities.drop: [ALL]`, CPU/memory requests and limits, `automountServiceAccountToken: false`.

![IaC report](screenshots/07-trivy-iac.png)

### 4.4 Static analysis (SAST): SonarQube with Quality Gate

SonarQube was already in the DevOps pipeline but only *reported*. It now **enforces** the Quality
Gate: `-Dsonar.qualitygate.wait=true` makes the build fail when the gate fails.

![SonarQube dashboard](screenshots/08-sonarqube.png)

### 4.5 Container security: image scan

**Tool:** Trivy `image`, run on the freshly built image **before** it is pushed to Docker Hub.

| | OS packages | Application (jar) |
|---|---|---|
| Before (`17-jdk`, Boot 3.5.5) | 70 CVEs (2 HIGH, 0 CRITICAL) | 71 CVEs (9 CRITICAL) |
| After (`17-jre`, patched deps) | 62 CVEs (2 HIGH, 0 CRITICAL) | 0 unaccepted CRITICAL |

The container runs as `uid=10001(app)`, verified with `docker run --entrypoint id`.

![Image scan report](screenshots/09-trivy-image.png)

---

## 5. Phase 2: Acceptance

### 5.1 Security acceptance tests: Gauntlt (Lab 3)

**Goal:** turn security requirements into executable BDD scenarios that run against the deployed
application after every deployment.

**Configuration:** `security/gauntlt/` contains a Dockerfile (Ruby 3.1 + gauntlt 1.0.13 + nmap + curl)
and two attack files:

| Attack file | Scenario | Expected |
|---|---|---|
| `nmap.attack` | Application port 8089 is reachable | `8089/tcp open` |
| `nmap.attack` | MySQL (3306/33060) is **not** exposed outside the cluster | ports not open |
| `http.attack` | Application is healthy | `/actuator/health` returns `UP` |
| `http.attack` | `/actuator/env` (configuration, secrets) is not exposed | 404 |
| `http.attack` | `/actuator/heapdump` (memory contents) is not exposed | 404 |
| `http.attack` | HTTP TRACE is disabled (Cross-Site Tracing) | not 200 |
| `http.attack` | Invalid input does not leak a Java stack trace | no `Exception` in body |

**Integration:** the stage runs after `Kubernetes Verify`, waits for the health endpoint, then runs
`gauntlt` in the container with host networking. The output is saved to `reports/gauntlt-report.txt`.

![Gauntlt results](screenshots/10-gauntlt.png)

---

## 6. Phase 3: Production

### 6.1 Security smoke test: OWASP ZAP Baseline

**Goal:** after each release, quickly check that the running application shows no obvious web
vulnerabilities (a security smoke test).

**Tool:** `zap-baseline.py` (OWASP ZAP), which spiders the application from Swagger UI for 2 minutes
and runs passive rules (security headers, cookies, information disclosure…).
Reports: `reports/zap/zap-baseline-report.html|json|md`. FAIL-level alerts mark the build UNSTABLE.

![ZAP baseline report](screenshots/11-zap.png)

### 6.2 Secrets management

No secret is stored in the repository or in the `Jenkinsfile`:

| Secret | Stored in | Used by |
|---|---|---|
| Docker Hub token | Jenkins credential `dockerhub-credentials` | Push stage (`--password-stdin`) |
| SonarQube token | Jenkins credential `sonar-token` | SAST stage |
| MySQL root password | Jenkins credential `mysql-root-password` → Kubernetes Secret `mysql-secret` | MySQL and Spring pods (`secretKeyRef`) |

Jenkins masks these values in the console log. The pre-commit stage (4.1) guarantees no new secret
is committed.

---

## 7. Phase 4: Operations

### 7.1 Continuous security monitoring: Prometheus alert rules

Prometheus already scraped the application (`/student/actuator/prometheus`). We added security
alert rules (`infra/monitoring/alert-rules.yml`):

| Alert | Detects | Expression (summary) |
|---|---|---|
| `StudentAppDown` | Application unreachable (DoS, failed deployment) | `up == 0` for 1 min |
| `SuspiciousClientErrorRate` | Bursts of 4xx: scanning, fuzzing, brute force | 4xx rate > 0.2 req/s |
| `ServerErrorRate` | 5xx errors under input or attack | 5xx rate > 0.1 req/s |
| `HeapExhaustion` | Memory exhaustion / memory DoS | heap > 90% for 5 min |

The **Continuous Monitoring Check** stage queries the Prometheus API after deployment and records
scrape-target health, loaded rules and firing alerts in `reports/monitoring-check.txt`.
The Gauntlt and ZAP stages generate attack-like traffic, so `SuspiciousClientErrorRate` fires
during the pipeline: the monitoring detects our own security tests.

![Prometheus alerts](screenshots/12-prometheus-alerts.png)
![Grafana dashboard](screenshots/13-grafana.png)

---

## 8. Reports produced by each build

| Report | Tool | Phase |
|---|---|---|
| `secrets-scan.txt` | pre-commit / HMRC hooks | Development |
| `trivy-sca-report.html/.txt` | Trivy (SCA) | Development |
| `trivy-iac-report.html/.txt` | Trivy (IaC) | Development |
| SonarQube project dashboard | SonarQube | Development |
| `trivy-image-report.html/.txt` | Trivy (image) | Development |
| `gauntlt-report.txt` | Gauntlt | Acceptance |
| `zap/zap-baseline-report.html/.json/.md` | OWASP ZAP | Production |
| `monitoring-check.txt` | Prometheus API | Operations |

All are archived by Jenkins (`archiveArtifacts 'reports/**'`) and downloadable from each build.

![Jenkins pipeline stage view](screenshots/01-jenkins-stage-view.png)
![Archived artifacts](screenshots/02-jenkins-artifacts.png)

## 9. Limits and next steps

- **Spring Boot 4 migration** to remove the two accepted SSE CVEs (review date 2027-01-31).
- **MySQL hardening:** use a non-root MySQL image (e.g. Bitnami) to fix the remaining IaC findings.
- **Base image CVEs:** 2 HIGH in Ubuntu packages without a fix yet; consider a distroless JRE image.
- **Authentication:** the API has no authentication. Adding Spring Security would be the next
  application-level control, and ZAP could then run an authenticated scan.
- **Alert routing:** connect Prometheus to Alertmanager (e-mail/Slack) so alerts reach the team.

## 10. How to run

1. `cd infra/vagrant && vagrant up` (Jenkins, SonarQube, Minikube, Prometheus, Grafana).
2. Jenkins: add the credentials `dockerhub-credentials`, `sonar-token`, `mysql-root-password`.
3. Job `student-management` (definition in `infra/jenkins/student-management-job.xml`) → **Build Now**.
4. Results: build page → *Artifacts* (`reports/`), SonarQube :9000, Prometheus :9090/alerts, Grafana :3000.
