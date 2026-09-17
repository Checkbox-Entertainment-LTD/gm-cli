pipeline {
    agent { label 'aurora01' }
    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 40, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '40'))
    }
    parameters {
        string(name: 'SOURCE_COMMIT', defaultValue: '', description: 'Exact pushed commit SHA; supplied by push events.')
    }
    environment {
        GH_BIN = '/home/frozenara/.local/lib/checkbox-runner/gh-2.100.0/gh'
    }
    stages {
        stage('Select exact commit') {
            steps {
                script {
                    if (!(params.SOURCE_COMMIT ==~ /[0-9a-f]{40}/)) { error('Full SOURCE_COMMIT required') }
                    env.CLI_COMMIT = params.SOURCE_COMMIT
                    dir("runs/${env.BUILD_NUMBER}/source") {
                        checkout(changelog: false, poll: false, scm: [$class: 'GitSCM',
                            branches: [[name: env.CLI_COMMIT]], userRemoteConfigs: scm.userRemoteConfigs,
                            extensions: [[$class: 'CloneOption', shallow: false, noTags: true]]])
                        def selected = sh(script: 'python3 ci/commit_policy.py --kind cli --commit "$CLI_COMMIT" --output ../selection.json --lines', returnStdout: true).trim().split('\n')
                        env.CLI_VERSION = selected[0]
                        env.CLI_NODE_BIN = sh(script: 'python3 ci/bootstrap_node.py', returnStdout: true).trim()
                        env.PUBLISH_CLI = selected[1]
                        env.SKIP_CLI = sh(script: 'test -f "$HOME/.local/share/checkbox-ci/cli/$CLI_COMMIT.json" && echo true || echo false', returnStdout: true).trim()
                    }
                    currentBuild.description = "CLI ${env.CLI_VERSION} / ${env.CLI_COMMIT.take(12)}"
                }
            }
        }
        stage('Test and build') {
            when { expression { env.SKIP_CLI != 'true' } }
            steps {
                dir("runs/${env.BUILD_NUMBER}/source") {
                    sh '''#!/bin/bash
set -euo pipefail
export PATH="$CLI_NODE_BIN:$PATH"
python3 -m unittest discover -s ci -p 'test_*.py' -q
python3 ci/release_cli.py stamp
npm ci
npm test
npm run build
python3 ci/check_packaged_cli.py
npm run lint
'''
                }
            }
        }
        stage('Publish version bump') {
            when { expression { env.SKIP_CLI != 'true' && env.PUBLISH_CLI == 'true' } }
            steps {
                dir("runs/${env.BUILD_NUMBER}/source") {
                    sh 'export PATH="$CLI_NODE_BIN:$PATH"; mkdir -p ../out && npm pack --ignore-scripts --pack-destination ../out'
                    withCredentials([gitUsernamePassword(credentialsId: 'Checkbox_Jenkins_GitHub_App')]) {
                        sh 'python3 ci/release_cli.py publish --package "../out/gamemaker-gm-cli-$CLI_VERSION.tgz"'
                    }
                }
                archiveArtifacts artifacts: "runs/${env.BUILD_NUMBER}/out/*", fingerprint: true
            }
        }
        stage('Record success') {
            steps {
                sh '''#!/bin/bash
set -euo pipefail
mkdir -p "$HOME/.local/share/checkbox-ci/cli"
cp "runs/$BUILD_NUMBER/selection.json" "$HOME/.local/share/checkbox-ci/cli/$CLI_COMMIT.json"
'''
                archiveArtifacts artifacts: "runs/${env.BUILD_NUMBER}/selection.json", fingerprint: true
            }
        }
    }
    post {
        success { dir("runs/${env.BUILD_NUMBER}") { deleteDir() } }
        failure { archiveArtifacts artifacts: "runs/${env.BUILD_NUMBER}/out/*,runs/${env.BUILD_NUMBER}/selection.json", allowEmptyArchive: true }
    }
}
