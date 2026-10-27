// Declarative pipeline for order-summary. The controller that runs it is defined by controller/casc/jenkins.yaml.
//   Verify (agent): Lint, Build, Test (unit and integration in parallel), Coverage
//   Approve (no agent): an optional manual approval that holds no executor while it waits
//   Publish (agent): uploads the jar with a token bound to that one step
pipeline {
    agent none

    parameters {
        booleanParam(name: 'REQUIRE_APPROVAL', defaultValue: false, description: 'Hold the publish step until a person approves it')
        booleanParam(name: 'ECHO_TOKEN', defaultValue: false, description: 'Make the publish step echo its token, to show that the log masks it')
        booleanParam(name: 'BREAK_A_TEST', defaultValue: false, description: 'Make one unit test fail, to show how a failing test is reported')
    }

    options {
        timeout(time: 20, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    environment {
        MVN = './mvnw --batch-mode --no-transfer-progress'
        JAR = 'order-summary-1.0.0.jar'
    }

    stages {
        stage('Verify') {
            agent { label 'docker-agent' }
            stages {
                stage('Lint') {
                    steps { dir('app') { sh "${MVN} checkstyle:check" } }
                }
                stage('Build') {
                    steps { dir('app') { sh "${MVN} -DskipTests package" } }
                }
                stage('Test') {
                    failFast true
                    parallel {
                        stage('Unit') {
                            steps {
                                dir('app') {
                                    withEnv(["BREAK_A_TEST=${params.BREAK_A_TEST}"]) { sh "${MVN} jacoco:prepare-agent@agent surefire:test" }
                                }
                            }
                            post { always { junit 'app/target/surefire-reports/*.xml' } }
                        }
                        stage('Integration') {
                            steps { dir('app') { sh "${MVN} failsafe:integration-test failsafe:verify" } }
                            post { always { junit 'app/target/failsafe-reports/*.xml' } }
                        }
                    }
                }
                stage('Coverage') {
                    steps {
                        dir('app') {
                            // jacoco skips quietly when it has no data, so require the unit tests' data file first.
                            sh "test -f target/jacoco-unit.exec && ${MVN} jacoco:report@report jacoco:check@coverage"
                        }
                    }
                }
            }
            post {
                success { stash name: 'jar', includes: 'app/target/*.jar', excludes: 'app/target/*-sources.jar' }
                always { sh 'pipeline/scripts/test-summary.sh app/target/surefire-reports app/target/failsafe-reports || true' }
            }
        }

        stage('Approve') {
            when { expression { params.REQUIRE_APPROVAL } }
            agent none
            options { timeout(time: 10, unit: 'MINUTES') }
            steps { input message: 'Publish order-summary?', ok: 'Publish', submitter: 'admin' }
        }

        stage('Publish') {
            agent { label 'docker-agent' }
            steps {
                unstash 'jar'
                // The token exists only inside this block, and only for the steps written here.
                withCredentials([string(credentialsId: 'publish-token', variable: 'TOKEN')]) {
                    script {
                        if (params.ECHO_TOKEN) {
                            sh 'echo "token=$TOKEN"'
                        }
                    }
                    sh 'pipeline/scripts/publish.sh "app/target/${JAR}"'
                }
            }
            post {
                success { archiveArtifacts artifacts: 'app/target/*.jar', fingerprint: true }
            }
        }
    }
}
