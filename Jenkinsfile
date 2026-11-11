pipeline {
    agent any

    // Jenkins credentials required (Manage Jenkins > Credentials):
    //   dockerhub-credentials  Username with password  Docker Hub login
    //   sonar-token            Secret text             SonarQube user token
    //   mysql-root-password    Secret text             MySQL root password used in Kubernetes
    environment {
        // Must start with the Docker Hub username stored in `dockerhub-credentials`
        IMAGE_NAME = 'youssefbouaouina82/student-management'
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        SONAR_HOST_URL = 'http://localhost:9000'
        // DevSecOps tooling runs in containers, so the VM needs nothing beyond Docker
        TRIVY_IMAGE = 'aquasec/trivy:0.65.0'
        PYTHON_IMAGE = 'python:3.12'
        ZAP_IMAGE = 'ghcr.io/zaproxy/zaproxy:stable'
        APP_URL = 'http://192.168.56.10:8089'        // the deployed app, as seen from outside
        PROMETHEUS_URL = 'http://localhost:9090'
    }

    stages {

        // ===================== DevSecOps Phase 1: Development =====================

        stage('Secrets Scan (pre-commit)') {
            // Lab 1: the same HMRC pre-commit hooks developers run locally, applied to
            // the whole repository. A leaked secret or key file fails the build.
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    mkdir -p reports "$HOME/.cache/pre-commit"
                    docker run --rm -u "$(id -u):$(id -g)" \
                      -e HOME=/tmp -e PRE_COMMIT_HOME=/cache -e PRE_COMMIT_COLOR=never \
                      -v "$WORKSPACE":/src -v "$HOME/.cache/pre-commit":/cache -w /src \
                      "$PYTHON_IMAGE" bash -c '
                        pip install -q --user --no-warn-script-location pre-commit &&
                        git config --global --add safe.directory /src &&
                        ~/.local/bin/pre-commit run --all-files' \
                      2>&1 | tee reports/secrets-scan.txt
                '''
            }
        }

        stage('Clean') {
            steps {
                sh 'mvn clean'
            }
        }

        stage('Compile') {
            steps {
                sh 'mvn compile'
            }
        }

        stage('Package') {
            steps {
                sh 'mvn package -DskipTests'
            }
        }

        stage('SCA + IaC Scan (Trivy)') {
            // Security Components Analysis (the Java equivalent of Lab 2 / Retire.js):
            // known CVEs in every library packaged in the Spring Boot jar.
            // IaC analysis: misconfigurations in the Dockerfile and k8s/ manifests.
            // Full reports are archived; unaccepted CRITICAL CVEs mark the build UNSTABLE
            // (accepted risks are documented in .trivyignore).
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    mkdir -p reports
                    HTML='--format template --template @/contrib/html.tpl'
                    SKIP='--skip-dirs lab1-evidence,lab-instructions,reports'
                    # SCA on the packaged application
                    bash security/trivy.sh rootfs --scanners vuln $HTML --output reports/trivy-sca-report.html target/
                    bash security/trivy.sh rootfs --scanners vuln --format table --output reports/trivy-sca-report.txt target/
                    # IaC analysis on Dockerfile + Kubernetes manifests
                    bash security/trivy.sh config $SKIP $HTML --output reports/trivy-iac-report.html .
                    bash security/trivy.sh config $SKIP --format table --output reports/trivy-iac-report.txt .
                    cat reports/trivy-sca-report.txt reports/trivy-iac-report.txt
                '''
                catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
                    sh 'bash security/trivy.sh rootfs --scanners vuln --severity CRITICAL --exit-code 1 --quiet target/'
                }
            }
        }

        stage('JS Dependency Scan (Retire.js)') {
            // Lab 2: Retire.js on the JavaScript libraries bundled in the application
            // (Swagger UI webjar). HIGH/CRITICAL vulnerable libraries mark the build UNSTABLE.
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
                    sh 'bash security/retire.sh'
                }
            }
        }

        stage('SonarQube Analysis (SAST)') {
            // Static analysis; the build now waits for and enforces the Quality Gate.
            steps {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    sh 'mvn sonar:sonar -Dsonar.host.url=$SONAR_HOST_URL -Dsonar.token=$SONAR_TOKEN -Dsonar.qualitygate.wait=true -Dsonar.qualitygate.timeout=300'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest ."
            }
        }

        stage('Container Scan (Trivy)') {
            // Container security: OS packages and libraries inside the image,
            // scanned before it is pushed. CRITICAL findings mark the build UNSTABLE.
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    mkdir -p reports
                    bash security/trivy.sh image --scanners vuln --format template --template @/contrib/html.tpl \
                      --output reports/trivy-image-report.html "$IMAGE_NAME:$IMAGE_TAG"
                    bash security/trivy.sh image --scanners vuln --format table \
                      --output reports/trivy-image-report.txt "$IMAGE_NAME:$IMAGE_TAG"
                    cat reports/trivy-image-report.txt
                '''
                catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
                    sh 'bash security/trivy.sh image --scanners vuln --severity CRITICAL --exit-code 1 --quiet "$IMAGE_NAME:$IMAGE_TAG"'
                }
            }
        }

        stage('Push Docker Image') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-credentials',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh 'echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin'
                    sh "docker push ${IMAGE_NAME}:${IMAGE_TAG}"
                    sh "docker push ${IMAGE_NAME}:latest"
                }
            }
        }

        stage('Kubernetes Deploy') {
            steps {
                withCredentials([string(credentialsId: 'mysql-root-password', variable: 'MYSQL_ROOT_PASSWORD')]) {
                    sh '''
                        kubectl apply -f k8s/namespace.yaml
                        kubectl -n devops create secret generic mysql-secret \
                          --from-literal=password="$MYSQL_ROOT_PASSWORD" \
                          --dry-run=client -o yaml | kubectl apply -f -
                        kubectl apply -f k8s/mysql.yaml
                    '''
                }
                sh "sed 's|__IMAGE__|${IMAGE_NAME}:${IMAGE_TAG}|' k8s/spring-app.yaml | kubectl apply -f -"
                sh 'kubectl -n devops rollout status deployment/spring-app --timeout=600s'
            }
        }

        stage('Kubernetes Verify') {
            steps {
                sh '''
                    echo "=== Pods ==="
                    kubectl get pods -n devops
                    echo "=== Services ==="
                    kubectl get svc -n devops
                    echo "=== Deployments ==="
                    kubectl get deployments -n devops
                '''
            }
        }

        // ===================== DevSecOps Phase 2: Acceptance =====================

        stage('Security Acceptance Tests (Gauntlt)') {
            // Lab 3: BDD security tests (security/gauntlt/*.attack) run against the
            // deployed application: network exposure (nmap) and HTTP hardening (curl).
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    mkdir -p reports
                    echo "Waiting for the application on $APP_URL ..."
                    for i in $(seq 1 36); do
                      curl -fs "$APP_URL/student/actuator/health" | grep -q UP && break
                      sleep 5
                    done
                    docker build -q -t devsecops/gauntlt security/gauntlt
                '''
                catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
                    sh '''#!/bin/bash
                        set -o pipefail
                        docker run --rm --network host -v "$WORKSPACE/security/gauntlt":/attacks \
                          devsecops/gauntlt 2>&1 | sed 's/\\x1b\\[[0-9;]*m//g' | tee reports/gauntlt-report.txt
                    '''
                }
            }
        }

        // ===================== DevSecOps Phase 3: Production =====================

        stage('Security Smoke Test (OWASP ZAP)') {
            // Passive DAST baseline scan of the running application (Production phase
            // "security smoke tests"). HTML/JSON reports are archived; WARN alerts are
            // reported, FAIL-level alerts mark the build UNSTABLE.
            steps {
                sh 'mkdir -p reports/zap && chmod 777 reports/zap'
                catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
                    sh '''#!/bin/bash
                        docker run --rm --network host -v "$WORKSPACE/reports/zap":/zap/wrk:rw \
                          "$ZAP_IMAGE" zap-baseline.py -t "$APP_URL/student/swagger-ui/index.html" \
                          -m 2 -I -r zap-baseline-report.html -J zap-baseline-report.json -w zap-baseline-report.md
                    '''
                }
            }
        }

        // ===================== DevSecOps Phase 4: Operations =====================

        stage('Continuous Monitoring Check') {
            // Shift right: the app must be scraped by Prometheus, and the security
            // alert rules (infra/monitoring/alert-rules.yml) must be loaded.
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    mkdir -p reports
                    # Simulated attack: ~100 s of requests to admin/login pages that do not
                    # exist (scanner / brute-force pattern). The SuspiciousClientErrorRate
                    # alert must detect it.
                    echo "Simulating a scanning / brute-force burst against $APP_URL ..."
                    for i in $(seq 1 400); do
                      curl -s -o /dev/null "$APP_URL/student/admin/login?attempt=$i" || true
                      sleep 0.2
                    done
                    sleep 30
                    python3 security/monitoring_check.py "$PROMETHEUS_URL" | tee reports/monitoring-check.txt
                '''
            }
        }
    }

    post {
        always {
            // Keep every security report with the build (Jenkins > build > Artifacts)
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
        success {
            echo 'Pipeline terminé avec succès!'
        }
        failure {
            echo 'Pipeline échoué!'
        }
    }
}
