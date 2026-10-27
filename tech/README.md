# Technology notes for jenkins-controller-as-code

These notes teach every technology this repository uses, from zero, through this repository's own files. Each file has the same nine parts: what it is, why it is here, where it appears, how it works underneath, a line-by-line walkthrough of this repository's use, commands to try, common mistakes, five questions, and official reading.

## Reading order

| # | File | Role in this repository |
| --- | --- | --- |
| 1 | [Bash](bash.md) | the scripts that start, run and stop everything |
| 2 | [GNU Make](make.md) | one-word commands (`make up`, `make test`) that wrap the scripts |
| 3 | [Git](git.md) | the source of truth the controller reads, and the tool for every change and rollback |
| 4 | [YAML](yaml.md) | the file format of every manifest and workflow |
| 5 | [Docker and the Dockerfile](docker.md) | builds the images and runs the containers the cluster uses |
| 6 | [Docker Compose](docker-compose.md) | starts the four services together and wires them |
| 7 | [nginx (the Git server)](nginx.md) | serves Git over HTTP to the Jenkins job |
| 8 | [Jenkins](jenkins.md) | the automation server this repository builds as code |
| 9 | [Jenkins Configuration as Code (JCasC)](jcasc.md) | the controller's configuration as one YAML file |
| 10 | [Jenkins plugins and the plugin lock](jenkins-plugins.md) | every plugin at an exact version, installed while the image is built |
| 11 | [Jenkins Pipeline (the Jenkinsfile)](jenkinsfile.md) | the pipeline definition: stages, approvals, credentials |
| 12 | [Groovy (in the Jenkinsfile and the Job DSL)](groovy.md) | the language of the Jenkinsfile and of the job definition |
| 13 | [Java 21](java.md) | the language of the project the pipeline builds |
| 14 | [Apache Maven](maven.md) | builds, tests and packages the Java project |
| 15 | [JUnit 5, AssertJ and ArchUnit](junit-assertj-archunit.md) | the Java test libraries |
| 16 | [JaCoCo and Checkstyle](jacoco-checkstyle.md) | the coverage rule and the style rules for the Java |
| 17 | [XML](xml.md) | the format of the POM, the Checkstyle rules and the test reports |
| 18 | [CSV](csv.md) | the input format of the order-summary program |
| 19 | [Python standard library (the publish-sink service)](publish-sink.md) | the artifact store the Publish stage uploads to |
| 20 | [curl, sed, grep, openssl, tar and other command-line tools](unix-tools.md) | the small programs the scripts call |
| 21 | [Python](python.md) | the language of the tests and a few helper scripts |
| 22 | [pip, venv and the lock files](pip-venv.md) | installs the exact test tools into a private folder |
| 23 | [TOML (pyproject.toml)](toml.md) | the one configuration file for the Python tools |
| 24 | [PyYAML](pyyaml.md) | reads the manifests in the offline tests |
| 25 | [pytest](pytest.md) | runs the offline tests and the cluster tests |
| 26 | [ruff](ruff.md) | lints and formats the Python |
| 27 | [mypy](mypy.md) | checks the type hints |
| 28 | [yamllint](yamllint.md) | checks the YAML files for style and mistakes |
| 29 | [ShellCheck](shellcheck.md) | finds mistakes in the shell scripts |
| 30 | [EditorConfig](editorconfig.md) | makes every editor use the same whitespace rules |
| 31 | [GitHub Actions](github-actions.md) | the CI workflow that repeats the checks on every push |

## Ten minutes? Read these three

- [Jenkins](jenkins.md): what a controller, an agent and a credential are, and why the controller runs no builds.
- [Jenkins Configuration as Code (JCasC)](jcasc.md): the single file that makes the controller reproducible.
- [Jenkins Pipeline (the Jenkinsfile)](jenkinsfile.md): the pipeline stage by stage, with the parallel tests and the approval.
