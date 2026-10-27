# The Jenkins controller, built only from files in this repository: a pinned image, an exact plugin list and the
# configuration-as-code file. No setup wizard, no plugin installed by hand.
ARG JENKINS_IMAGE=jenkins/jenkins:2.580.1-lts-jdk21@sha256:a660310e39ade10631f774bacd5219de767dfd08947ea5c32a739b5e5bb382c1
FROM ${JENKINS_IMAGE}

ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/usr/share/jenkins/casc_configs/jenkins.yaml

# plugins.lock.txt names every plugin, transitive ones included, at an exact version (see `make plugins-lock`).
COPY plugins.lock.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# Outside JENKINS_HOME on purpose: a volume mounted there must not hide the configuration.
COPY casc/jenkins.yaml /usr/share/jenkins/casc_configs/jenkins.yaml

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=30 \
  CMD curl -fsS http://localhost:8080/login -o /dev/null || exit 1
