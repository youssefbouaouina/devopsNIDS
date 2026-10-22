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
    }

    stages {

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

        stage('SonarQube Analysis') {
            steps {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    sh 'mvn sonar:sonar -Dsonar.host.url=$SONAR_HOST_URL -Dsonar.token=$SONAR_TOKEN'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest ."
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
                sh 'kubectl -n devops rollout status deployment/spring-app --timeout=300s'
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
    }

    post {
        success {
            echo 'Pipeline terminé avec succès!'
        }
        failure {
            echo 'Pipeline échoué!'
        }
    }
}
