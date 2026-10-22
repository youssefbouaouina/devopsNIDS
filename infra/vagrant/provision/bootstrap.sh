#!/usr/bin/env bash
# One-time toolchain install (runs as root on first `vagrant up`).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Jenkins apt repo goes in first so a single `apt-get update` covers everything
# (and a stale repo entry from an earlier run can't break the update).
echo "==> Jenkins apt repository"
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key -o /etc/apt/keyrings/jenkins-keyring.asc
echo "deb [signed-by=/etc/apt/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" \
  > /etc/apt/sources.list.d/jenkins.list

echo "==> Base packages, JDK, Maven, Git"
apt-get update -y
apt-get install -y ca-certificates curl gnupg git maven socat openjdk-21-jdk-headless

echo "==> Docker"
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker
usermod -aG docker vagrant

echo "==> Jenkins"
apt-get install -y jenkins
usermod -aG docker jenkins
systemctl enable jenkins
systemctl restart jenkins

echo "==> kubectl + Minikube"
KUBECTL_VERSION="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
chmod +x /usr/local/bin/kubectl
curl -fsSLo /usr/local/bin/minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
chmod +x /usr/local/bin/minikube

echo "==> Kernel settings required by SonarQube (Elasticsearch)"
cat > /etc/sysctl.d/99-sonarqube.conf <<'EOF'
vm.max_map_count=524288
fs.file-max=131072
EOF
sysctl --system >/dev/null

echo "==> Bootstrap done"
