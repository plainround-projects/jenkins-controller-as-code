# Git

## 1. What it is

Git is a version-control system: it stores the history of a folder as a chain of **commits**, each a snapshot with a message and a parent. A **repository** is that history. A **remote** is another copy (here a small server inside the cluster). `push` sends commits to a remote; `clone` copies one.

## 2. Why this repository uses it

Jenkins builds from a Git repository. The stack contains its own small Git server, and `make seed` pushes a snapshot of this repository to it, so the job's `Jenkinsfile` and code come from Git, not from a folder.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `scripts/seed-project.sh` | builds a clean snapshot repository and force-pushes it |
| `services/git-server/` | the smart-HTTP Git server image |
| `controller/casc/jenkins.yaml` | the job's `scm { git { remote { url(...) } branches('*/main') } }` |
| `.gitignore` | keeps `.env`, `.venv`, `app/target` out of Git |

## 4. How it works underneath

- A commit is identified by a 40-character hash of its content and parent. Changing anything changes the hash, so a hash names exactly one state.
- A **branch** is a movable name for a commit (`main`). `HEAD` is "where I am now".
- `git revert <commit>` makes a *new* commit that undoes an earlier one. History is kept, so it is the safe way to undo a shared change.
- A **hook** is a script Git runs at a moment such as `pre-push`; if it exits non-zero, the push is refused. `--no-verify` skips it.
- **Smart HTTP**: the server answers `GET .../info/refs?service=git-upload-pack` to list branches and `POST .../git-receive-pack` to accept a push. Anything that speaks that can be a Git server.

## 5. Walkthrough of this repository's use

```bash
git -C "${snapshot}" init --quiet --initial-branch=main
git -C "${snapshot}" config user.name "Seed"
git -C "${snapshot}" config user.email "seed@example.invalid"
git -C "${snapshot}" config commit.gpgsign false
git -C "${snapshot}" add --all
git -C "${snapshot}" commit --quiet -m "Snapshot of controller-as-code"
git -C "${snapshot}" push --quiet --force "http://127.0.0.1:${GIT_PORT}/controller-as-code.git" main
```
`-C <dir>` runs Git as if started in that folder. A fresh repository, a fixed author and signing off (so a global Git setting cannot block the script), one commit and a **force** push (replace whatever is on the server). The URL is the host port of the Git server container; the job inside the Docker network reaches it at `http://git-server:8080/controller-as-code.git` (the service name is a DNS name inside the Compose network). In `jenkins.yaml` the job says `branches('*/main')`: build the `main` branch. `lightweight(true)` tells Jenkins to fetch only the `Jenkinsfile` when it only needs to read the pipeline definition.

The Git server is a small image of nginx + `git-http-backend` through `fcgiwrap` + `tini` (see the nginx note), with a bare repository created at start-up (`REPOS: controller-as-code` in the Compose file).

## 6. Try it yourself

1. `make seed` : prints `seeded controller-as-code at <hash>`.
2. `git ls-remote http://127.0.0.1:18480/controller-as-code.git` : the branch `refs/heads/main`.
3. `git ls-files --cached --others --exclude-standard | head` : the files that would be in the snapshot.
4. `git status --short` : clean.
5. In Jenkins, open the job's *Git polling log* or the build's console: `Checking out Revision <hash>`.

## 7. Mistakes people make

- Rewriting shared history (`push --force`) so other copies disagree. The runbook uses `revert`, and `--force` only on the demo repository when it is reset.
- Committing generated files or secrets. `.gitignore` lists what must not be tracked.
- Assuming a hook cannot be skipped. A hook is a convenience; the real gate is a check on the server or in CI.

## 8. Check yourself

1. What does a commit hash identify?
   *Answer:* Exactly one snapshot and its history.
2. Why use `git revert` instead of deleting a commit?
   *Answer:* It adds a new commit that undoes the old one and keeps the history intact.
3. What is a pre-push hook?
   *Answer:* A script that runs before a push and can refuse it by failing.
4. How can a hook be skipped?
   *Answer:* With `git push --no-verify`.
5. What is `main`?
   *Answer:* A branch name: a pointer to the newest commit of the main line.

## 9. Further reading

- Pro Git book: <https://git-scm.com/book/en/v2>. Git reference: <https://git-scm.com/docs>.
