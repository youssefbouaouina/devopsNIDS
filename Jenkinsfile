pipeline {
    agent any

    environment {
        IMAGE_NAME = 'youssefbouaouina/student-management'
        IMAGE_TAG = '1.0'
    }

    stages {

        stage('GIT') {
            steps {
                echo "Getting Project from Git"
                git branch: 'master', url: 'https://github.com/youssefbouaouina/devopsNIDS.git'
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

        stage('SonarQube Analysis') {
            steps {
                sh '''mvn sonar:sonar \
                  -Dsonar.host.url=http://192.168.198.131:9000 \
                  -Dsonar.login=admin \
                  -Dsonar.password=Pass123'''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
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
                }
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