# Hardened runtime image (DevSecOps remediation of Trivy findings):
# - JRE instead of the full JDK: smaller image, fewer OS packages, fewer CVEs
# - runs as a dedicated non-root user (Trivy AVD-DS-0002)
FROM eclipse-temurin:17-jre

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --chown=app:app target/*.jar app.jar

USER 10001

EXPOSE 8089

ENTRYPOINT ["java", "-jar", "app.jar"]
