# Groovy (in the Jenkinsfile and the Job DSL)

## 1. What it is

Groovy is a programming language for the Java virtual machine. Its syntax is close to Java's but looser: semicolons are optional, strings can contain `${expressions}`, and blocks of code can be passed around as **closures**. Jenkins uses Groovy for pipelines (`Jenkinsfile`) and for the Job DSL (the job definition inside `jenkins.yaml`).

## 2. Why this repository uses it

You cannot read a Jenkinsfile without a few Groovy rules. This note lists exactly the ones this repository's two Groovy snippets use.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `Jenkinsfile` | declarative pipeline in Groovy syntax |
| `controller/casc/jenkins.yaml (`jobs: - script: >`)` | a Job DSL script that creates the pipeline job |

## 4. How it works underneath

- A **closure** is a block of code in braces: `{ sh 'ls' }`. A method call with a closure as last argument can omit parentheses: `steps { ... }` is `steps({ ... })`.
- A **map** is `[key: value]`; named arguments are written `name: value` (`booleanParam(name: 'X', defaultValue: false)`).
- Strings: `'single'` is literal; `"double ${expr}"` interpolates expressions (a GString).
- Groovy is *dynamic*: `params.REQUIRE_APPROVAL` looks up a property by name at run time.
- Jenkins runs pipeline Groovy in a special interpreter (the CPS transformer) so a build can pause and resume; not every Java/Groovy library call is allowed there.

## 5. Walkthrough of this repository's use

```groovy
sh "${MVN} checkstyle:check"
```
A double-quoted string: Groovy replaces `${MVN}` with the value defined in `environment { MVN = '...' }`, and the final text goes to the shell.

```groovy
withEnv(["BREAK_A_TEST=${params.BREAK_A_TEST}"]) { sh "${MVN} jacoco:prepare-agent@agent surefire:test" }
```
A **list** `[...]` with one interpolated string is the argument; the braces after it are a closure with the steps to run with that environment.

```groovy
when { expression { params.REQUIRE_APPROVAL } }
```
Two nested closures: `expression { ... }` returns a boolean.

```groovy
script { if (params.ECHO_TOKEN) { sh 'echo "token=$TOKEN"' } }
```
Inside `script { }` you may use ordinary statements such as `if`. In `'echo "token=$TOKEN"'` the single quotes keep `$TOKEN` for the shell.

The Job DSL in `jenkins.yaml`:
```groovy
pipelineJob('order-summary') {
  description('...')
  parameters { booleanParam('REQUIRE_APPROVAL', false, '...') }
  definition { cpsScm { scm { git { remote { url('http://git-server:8080/controller-as-code.git') }; branches('*/main') } }; scriptPath('Jenkinsfile'); lightweight(true) } }
}
```
Every `name { ... }` is a method call taking a closure; `url('...')` and `branches('*/main')` are method calls with a string. It reads like configuration but it is code run once when the controller starts.

## 6. Try it yourself

1. In *Manage Jenkins > Script Console* (admin only): `println "hello ${1 + 1}"` : `hello 2`.
2. `println(['a', 'b'].collect { it.toUpperCase() })` : `[A, B]` (a closure with the implicit argument `it`).
3. `make lint-jenkinsfile` : the structure is valid declarative syntax.
4. `grep -n 'script' Jenkinsfile` : the one `script { }` block.
5. In the script console: `println Jenkins.instance.getItem('order-summary').class` : the job created by the Job DSL.

## 7. Mistakes people make

- Using `"..."` when the text contains `$` that belongs to the shell (use `'...'`).
- Calling an unsafe API from a sandboxed pipeline: Jenkins refuses it unless approved.
- Writing long programs in the Jenkinsfile. Put logic in scripts.

## 8. Check yourself

1. What is a closure?
   *Answer:* A block of code in braces that can be passed to a method.
2. What is the difference between `'x'` and `"x"` in Groovy?
   *Answer:* Double quotes interpolate `${...}`; single quotes do not.
3. Why can `steps { ... }` have no parentheses?
   *Answer:* A method call whose last argument is a closure can omit them.
4. What runs the Job DSL script?
   *Answer:* The Job DSL plugin, when the controller applies its configuration.
5. Why `script { }` inside a declarative stage?
   *Answer:* To use ordinary Groovy statements like `if`.

## 9. Further reading

- Groovy language documentation: <https://groovy-lang.org/documentation.html>. Job DSL: <https://jenkinsci.github.io/job-dsl-plugin/>.
