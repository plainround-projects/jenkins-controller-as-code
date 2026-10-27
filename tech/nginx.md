# nginx (the Git server)

## 1. What it is

nginx is a web server. Here it fronts `git-http-backend` (through `fcgiwrap`) so Jenkins can clone the repository over plain HTTP.

## 2. Why this repository uses it

The job builds from Git, and the stack has no GitHub. A small Git server in the Compose project keeps the lesson self-contained.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `services/git-server/nginx.conf` | the server's whole configuration |
| `services/git-server/Dockerfile, entrypoint.sh` | the image and the start-up script |
| `docker-compose.yml` | the service with a read-only root file system and a tmpfs `/tmp` |

## 4. How it works underneath

- A `server { listen 8080; ... }` block defines a virtual server; `location = /path` matches exactly that path and `location ~ regex` matches a regular expression.
- `return 200 "ok
";` answers directly.
- nginx does not know Git. It hands Git protocol requests over **FastCGI** (a simple protocol between a web server and a program) to `fcgiwrap`, which runs the program `git-http-backend`. Git's *smart HTTP* has a few paths: `GET info/refs?service=git-upload-pack` lists branches, `POST git-upload-pack` fetches, `POST git-receive-pack` pushes.
- `tini` is a tiny init process: it is process 1 in the container, passes signals on and cleans up finished child processes.

## 5. Walkthrough of this repository's use

In short:
* `worker_processes 1;`, `pid /tmp/nginx.pid;`, `error_log /dev/stderr info;` and `access_log /dev/stdout;` keep every path writable-by-design (`/tmp`) or a stream, because the container's root file system is read-only and it runs as uid 10001.
* `location = /healthz { return 200 "ok\n"; }` for the health check.
* `location ~ ^/.+\.git/(HEAD|info/refs|objects/info/.*|git-(upload|receive)-pack)$ { ... fastcgi_pass unix:/tmp/fcgiwrap.sock; fastcgi_param SCRIPT_FILENAME /usr/libexec/git-core/git-http-backend; fastcgi_param GIT_PROJECT_ROOT /srv/git; fastcgi_param GIT_HTTP_EXPORT_ALL ""; ... }` passes Git protocol requests to `git-http-backend`.
* `entrypoint.sh` creates a bare repository for each name in `REPOS` (`controller-as-code`), starts `fcgiwrap` in the background on a Unix socket and `exec`s nginx in the foreground (`daemon off;`).

In this stack the repository is created empty and filled by `scripts/seed-project.sh` (a force-push). There is no authentication: the port is published on `127.0.0.1` only.

## 6. Try it yourself

1. `curl -s 'http://127.0.0.1:18480/controller-as-code.git/info/refs?service=git-upload-pack' | head -c 150` : Git's ref advertisement.
2. `git ls-remote http://127.0.0.1:18480/controller-as-code.git` : `refs/heads/main`.
3. `docker compose logs --tail 10 git-server` : the access log lines from Jenkins's checkouts.
4. `docker compose exec git-server ls /srv/git` : `controller-as-code.git`.
5. `docker compose exec git-server sh -c 'touch /etc/x'` : fails (read-only root file system).

## 7. Mistakes people make

- Listening on port 80 as a non-root user (ports below 1024 need root); this server listens on 8080.
- Letting nginx write to a read-only file system; its pid file, temp paths and sockets are under `/tmp` (a tmpfs).
- Exposing an unauthenticated Git server beyond the loopback interface. The port is published on `127.0.0.1` only.

## 8. Check yourself

1. How does nginx serve Git?
   *Answer:* It forwards Git protocol paths over FastCGI to `fcgiwrap`, which runs `git-http-backend`.
2. Why are pid and temp paths under `/tmp`?
   *Answer:* The container runs as a non-root user with a read-only root file system.
3. What does `exec nginx -g 'daemon off;'` do in the entrypoint?
   *Answer:* Replaces the shell with nginx in the foreground so it receives signals directly.
4. What does the regular-expression `location` match?
   *Answer:* Only the Git protocol paths of a repository whose name ends in `.git`.
5. Why no authentication?
   *Answer:* It is a local teaching server reachable only on 127.0.0.1.

## 9. Further reading

- nginx: <https://nginx.org/en/docs/>. `git-http-backend`: <https://git-scm.com/docs/git-http-backend>.
