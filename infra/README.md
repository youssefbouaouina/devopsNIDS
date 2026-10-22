# DevOps lab: complete setup guide

How to rebuild and run the full CI/CD chain for `student-management` on a Windows machine,
from nothing to a deployed, monitored app.

```
 GitHub ──▶ Jenkins ──▶ Maven ──▶ SonarQube ──▶ Docker Hub ──▶ Minikube ──▶ Prometheus ──▶ Grafana
 (code)     (CI/CD)    (build)   (quality)     (images)      (Spring+MySQL)  (metrics)    (dashboards)
```

Everything except Windows tools runs inside **one Ubuntu VM** created by Vagrant:

| Inside the VM         | How it runs                         | Port  |
|-----------------------|-------------------------------------|-------|
| Jenkins               | native service (`systemctl`)        | 8080  |
| JDK 21, Maven, Git    | native packages (used by Jenkins)   |       |
| SonarQube             | Docker container                    | 9000  |
| Minikube (Kubernetes) | Docker driver, namespace `devops`   |       |
| MySQL + Spring app    | Pods in Minikube                    | 8089 (forwarded) |
| Prometheus            | Docker container                    | 9090  |
| Grafana               | Docker container                    | 3000  |

VM address from Windows: **`192.168.56.10`**

---

## Part 1: Windows prerequisites (once per machine)

> Already done on this machine: VirtualBox 7.2, Vagrant 2.4.9 and Git are installed.

1. **VirtualBox**: https://www.virtualbox.org/wiki/Downloads, install with defaults.
2. **Vagrant**: https://developer.hashicorp.com/vagrant/install (Windows AMD64 MSI), install, reboot when asked.
3. **Git**: https://git-scm.com/download/win
4. Check in a **new** PowerShell window:
   ```powershell
   vagrant --version
   git --version
   ```

**Resources:** the VM takes 10 GB RAM and 6 CPUs. On a 16 GB machine, close Docker Desktop and heavy
apps while the lab runs. To use less RAM: `$env:VM_MEMORY=8192; $env:VM_CPUS=4` before `vagrant up`.

---

## Part 2: Get the code

```powershell
cd C:\Users\SidikRoyale\Documents\projects
git clone https://github.com/youssefbouaouina/devopsNIDS.git   # skip if the folder already exists
cd devopsNIDS
```

> **Important:** Jenkins builds whatever is on **GitHub**, not your local folder. The lab files
> (`infra/`, `k8s/`, the updated `Jenkinsfile` and `pom.xml`) must be committed and pushed before the
> pipeline can use them (see Part 5).

---

## Part 3: Create the VM

```powershell
cd C:\Users\SidikRoyale\Documents\projects\devopsNIDS\infra\vagrant
vagrant up
```

First run: 15 to 30 minutes. It downloads the Ubuntu 24.04 box, then:

- `bootstrap.sh` (first run only): installs JDK, Maven, Git, Docker, Jenkins, kubectl, Minikube.
- `services.sh` (every `vagrant up`): starts Minikube, gives Jenkins the cluster config,
  starts SonarQube, Prometheus and Grafana, and forwards port 8089 to the app.

It ends with a box listing all URLs. Check the VM:

```powershell
vagrant status            # should say: running (virtualbox)
vagrant ssh               # open a shell inside the VM (type `exit` to leave)
```

Inside the VM, a quick health check:

```bash
systemctl is-active jenkins          # active
docker ps                            # sonarqube, prometheus, grafana, minikube
minikube status                      # host/kubelet/apiserver: Running
```

> SonarQube needs 1 to 2 minutes after the VM boots before its page loads.

---

## Part 4: One-time configuration of the tools

### 4.1 Jenkins: unlock and create the admin user

1. Get the unlock password (PowerShell, in `infra\vagrant`):
   ```powershell
   vagrant ssh -c "sudo cat /var/lib/jenkins/secrets/initialAdminPassword"
   ```
2. Open http://192.168.56.10:8080 and paste it.
3. Click **Install suggested plugins** and wait.
4. Create your admin user (your own username and password).
5. Instance URL: keep `http://192.168.56.10:8080/`, then **Save and Finish**.

The suggested plugins include everything the Jenkinsfile needs (Pipeline, Git, Credentials Binding).

### 4.2 SonarQube: change the password and create a token

1. Open http://192.168.56.10:9000 and log in as `admin` / `admin`.
2. Set a new password when prompted.
3. Top-right avatar, then **My Account > Security**.
4. Generate token: Name `jenkins`, Type **Global Analysis Token**, Expiration as you like.
5. **Copy the token now** (it is shown only once).

### 4.3 Docker Hub: access token

1. Log in at https://hub.docker.com.
2. **Account settings > Personal access tokens > Generate new token**, permissions **Read & Write**.
3. Copy the token.

> The pipeline pushes to `youssefbouaouina/student-management`. If your Docker Hub username is different,
> change `IMAGE_NAME` at the top of the `Jenkinsfile`.

### 4.4 GitHub: access token (the repo is private)

1. GitHub, **Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token**.
2. Repository access: **Only select repositories**, then `devopsNIDS`.
3. Permissions: **Contents: Read-only**.
4. Copy the token.

### 4.5 Jenkins: add the credentials

Jenkins, **Manage Jenkins > Credentials > System > Global credentials > Add Credentials**.
Create these four. The **ID must match exactly**, because the Jenkinsfile looks them up by ID.

| Kind                    | ID                      | Fill in                                                |
|-------------------------|-------------------------|--------------------------------------------------------|
| Username with password  | `github-credentials`    | Username: your GitHub username. Password: the GitHub token (4.4) |
| Username with password  | `dockerhub-credentials` | Username: Docker Hub username. Password: Docker Hub token (4.3) |
| Secret text             | `sonar-token`           | Secret: the SonarQube token (4.2)                      |
| Secret text             | `mysql-root-password`   | Secret: any password you choose for the in-cluster MySQL |

### 4.6 Jenkins: create the pipeline job

1. **Dashboard > New Item**, name `student-management`, type **Pipeline**, then **OK**.
2. *(Optional)* **Triggers**: tick **Poll SCM**, schedule `H/5 * * * *` (checks GitHub every 5 minutes;
   GitHub webhooks can't reach this VM's private IP).
3. **Pipeline** section:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `https://github.com/youssefbouaouina/devopsNIDS.git`
   - Credentials: `github-credentials`
   - Branch Specifier: `*/master` (or `*/infra/vagrant-devops-lab` until that branch is merged)
   - Script Path: `Jenkinsfile`
4. **Save**.

---

## Part 5: Run the pipeline

1. Push the lab files to GitHub (from the repo root on Windows):
   ```powershell
   git add .
   git commit -m "Add Vagrant DevOps lab, k8s manifests and monitoring"
   git push -u origin infra/vagrant-devops-lab
   ```
   Then merge into `master` (Pull Request on GitHub), or point the job at the branch (4.6).
2. In Jenkins, open `student-management` and click **Build Now**.
3. Click the build number, then **Console Output** to follow it.

What each stage does:

| Stage              | What happens                                                     |
|--------------------|------------------------------------------------------------------|
| Clean / Compile / Package | `mvn clean`, `mvn compile`, `mvn package -DskipTests` → `target/*.jar` |
| SonarQube Analysis | Sends the code to SonarQube; results at http://192.168.56.10:9000 |
| Build Docker Image | Builds `youssefbouaouina/student-management:<build#>` and `:latest` |
| Push Docker Image  | Pushes both tags to Docker Hub                                    |
| Kubernetes Deploy  | Applies `k8s/`: namespace `devops`, MySQL secret, MySQL, Spring app; waits for rollout |
| Kubernetes Verify  | Prints pods, services and deployments                            |

The first build is slow because Maven downloads every dependency. Later builds are faster.

---

## Part 6: Check the deployed app

From Windows:

- Swagger UI: http://192.168.56.10:8089/student/swagger-ui.html
- Health: http://192.168.56.10:8089/student/actuator/health
- API, for example: http://192.168.56.10:8089/student/students/getAllStudents

Create a student from PowerShell:

```powershell
$body = '{"firstName":"Ali","lastName":"Ben Salah","email":"ali@example.com","phone":"12345678","dateOfBirth":"2000-01-15","address":"Tunis"}'
Invoke-RestMethod -Method Post -Uri http://192.168.56.10:8089/student/students/createStudent -ContentType 'application/json' -Body $body
Invoke-RestMethod http://192.168.56.10:8089/student/students/getAllStudents
```

Inside the VM (`vagrant ssh`):

```bash
kubectl get all -n devops
kubectl logs -n devops deploy/spring-app -f       # app logs (Ctrl+C to stop)
kubectl logs -n devops deploy/mysql
minikube dashboard --url                           # Kubernetes web dashboard
```

API endpoints (all under `/student`):

| Resource    | Base path      | Endpoints |
|-------------|----------------|-----------|
| Students    | `/students`    | `getAllStudents`, `getStudent/{id}`, `createStudent`, `updateStudent`, `deleteStudent/{id}` |
| Departments | `/Depatment`   | `getAllDepartment`, `getDepartment/{id}`, `createDepartment`, `updateDepartment`, `deleteDepartment/{id}` |
| Enrollments | `/Enrollment`  | `getAllEnrollment`, `getEnrollment/{id}`, `createEnrollment`, `updateEnrollment`, `deleteEnrollment/{id}` |

---

## Part 7: Monitoring

**Prometheus**: http://192.168.56.10:9090

- **Status > Targets**: `student-management` should be **UP** once the app is deployed.
- Try a query: `http_server_requests_seconds_count` or `jvm_memory_used_bytes`.

**Grafana**: http://192.168.56.10:3000

1. Log in as `admin` / `admin`, then set a new password.
2. The **Prometheus** data source is already configured (Connections > Data sources).
3. **Dashboards > New > Import**, enter ID **4701** (JVM Micrometer), **Load**, choose *Prometheus*, **Import**.
   Also good: **19004** (Spring Boot 3.x Statistics).

---

## Part 8: Daily use

Run in `infra\vagrant`:

| Action                         | Command            |
|--------------------------------|--------------------|
| Start the lab                  | `vagrant up`       |
| Stop it (frees RAM)            | `vagrant halt`     |
| Pause, keeping state           | `vagrant suspend` / `vagrant resume` |
| Shell into the VM              | `vagrant ssh`      |
| Re-run the setup scripts       | `vagrant provision`|
| Delete the VM completely       | `vagrant destroy`  |

After `vagrant up` everything restarts automatically: Jenkins, SonarQube, monitoring, Minikube, and
the app pods with their MySQL data. Jenkins jobs, SonarQube projects and Grafana dashboards persist
until `vagrant destroy`.

---

## Part 9: Troubleshooting

| Symptom | Fix |
|---------|-----|
| `vagrant up` fails with VT-x / Hyper-V errors | Enable virtualization in BIOS. VirtualBox 7 can run alongside Hyper-V/WSL2 but is slower; to free it: `bcdedit /set hypervisorlaunchtype off` (admin), reboot (this disables WSL2/Docker Desktop until set back to `auto`). |
| Page at `192.168.56.10` doesn't load | `vagrant status` must be *running*. Then `vagrant ssh` → `docker ps` / `systemctl status jenkins`. |
| SonarQube container keeps restarting | `docker logs sonarqube`. Usually memory: give the VM more RAM, or check `sysctl vm.max_map_count` is `524288`. |
| Pipeline: `permission denied ... docker.sock` | `sudo systemctl restart jenkins` (it needs a restart to pick up the docker group). |
| Pipeline: `kubectl ... connection refused` | Minikube is down: `vagrant provision --provision-with services`. |
| Pipeline: `credentials ... could not be found` | A credential ID in Jenkins doesn't exactly match the table in 4.5. |
| Pod `ImagePullBackOff` | The Docker Hub push failed or the image name doesn't match your account (`IMAGE_NAME`). |
| Pod `CrashLoopBackOff` | `kubectl logs -n devops deploy/spring-app`. Usually MySQL not ready yet; it recovers by itself after about a minute. |
| Prometheus target DOWN | App not deployed yet, or the forward is down: `sudo systemctl restart spring-app-forward`. |

---

## What changed compared with the original setup

- Kubernetes manifests now live in the repo (`k8s/`) instead of `/home/vagrant/k8s-student/` on the VM.
- Secrets (SonarQube token, Docker Hub, MySQL password) are Jenkins credentials, not hardcoded in the `Jenkinsfile`.
- Images are tagged with the Jenkins build number, so each build actually rolls out a new version.
- The app exposes `/actuator/health` and `/actuator/prometheus` for Kubernetes probes and Prometheus.
- The whole VM is defined in code (`infra/vagrant`), so `vagrant destroy && vagrant up` rebuilds it.
