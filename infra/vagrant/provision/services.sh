#!/usr/bin/env bash
# Runs as root on every `vagrant up`: brings up the cluster and the supporting services.
set -euo pipefail

VM_IP="$(hostname -I | tr ' ' '\n' | grep '^192\.168\.56\.' | head -1)"
as_vagrant() { su - vagrant -c "$*"; }

echo "==> Minikube"
as_vagrant "minikube start --driver=docker --memory=3072 --cpus=2"
MINIKUBE_IP="$(as_vagrant 'minikube ip')"

echo "==> Give Jenkins access to the cluster"
install -d -o jenkins -g jenkins /var/lib/jenkins/.kube
as_vagrant "kubectl config view --flatten --minify" > /var/lib/jenkins/.kube/config
chown jenkins:jenkins /var/lib/jenkins/.kube/config
chmod 600 /var/lib/jenkins/.kube/config

echo "==> Expose the Spring NodePort on the VM (:8089 -> ${MINIKUBE_IP}:30089)"
cat > /etc/systemd/system/spring-app-forward.service <<EOF
[Unit]
Description=Forward VM port 8089 to the student-management NodePort in Minikube
After=network-online.target docker.service

[Service]
ExecStart=/usr/bin/socat TCP-LISTEN:8089,fork,reuseaddr TCP:${MINIKUBE_IP}:30089
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable spring-app-forward
systemctl restart spring-app-forward

echo "==> SonarQube"
if ! docker inspect sonarqube >/dev/null 2>&1; then
  docker run -d --name sonarqube --restart unless-stopped -p 9000:9000 \
    -v sonarqube_data:/opt/sonarqube/data \
    -v sonarqube_extensions:/opt/sonarqube/extensions \
    -v sonarqube_logs:/opt/sonarqube/logs \
    sonarqube:community
else
  docker start sonarqube >/dev/null
fi

echo "==> Prometheus + Grafana"
docker compose -f /vagrant/infra/monitoring/docker-compose.yml up -d

cat <<EOF

================ DevOps lab is up ================
 Jenkins     http://${VM_IP}:8080
             first-login password: vagrant ssh -c "sudo cat /var/lib/jenkins/secrets/initialAdminPassword"
 SonarQube   http://${VM_IP}:9000   (first login admin/admin, then change it)
 Prometheus  http://${VM_IP}:9090
 Grafana     http://${VM_IP}:3000   (first login admin/admin, then change it)
 Spring app  http://${VM_IP}:8089/student/swagger-ui.html   (after the first pipeline run)
==================================================
EOF
