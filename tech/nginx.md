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





<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of `services/git-server/nginx.conf`

nginx is a web server. Its configuration is a tree of *directives* (`name value;`) and *blocks* (`name { ... }`). `git-http-backend` is a program shipped with Git that speaks the "smart HTTP" protocol (what `git clone http://...` and `git push http://...` use); nginx cannot run it directly, so it hands requests to `fcgiwrap`, which runs it as a CGI program.

```nginx
worker_processes 1;
pid /tmp/nginx.pid;
error_log /dev/stderr info;

events { worker_connections 64; }

http {
  access_log /dev/stdout;
  client_body_temp_path /tmp/nginx-body;
  proxy_temp_path /tmp/nginx-proxy;
  fastcgi_temp_path /tmp/nginx-fastcgi;
  uwsgi_temp_path /tmp/nginx-uwsgi;
  scgi_temp_path /tmp/nginx-scgi;
```
- `worker_processes 1;` runs one worker, enough for a demo.
- `pid /tmp/nginx.pid;` writes the process id to `/tmp` because the container's root filesystem is read-only.
- `error_log /dev/stderr info;` sends errors to standard error so `docker compose logs` shows them.
- `events { worker_connections 64; }` limits simultaneous connections per worker.
- `http {` starts the web-server settings. `access_log /dev/stdout;` writes each request to standard output.
- Lines 9-13 move nginx's temporary directories (request bodies, proxying, FastCGI, uwsgi, scgi) into `/tmp`, the only writable place; without this nginx would try to write under `/var/lib` and fail.

```nginx
  server {
    listen 8080;
    client_max_body_size 50m;

    location = /healthz {
      default_type text/plain;
      return 200 "ok\n";
    }
```
`server {` defines one virtual server. `listen 8080;` is the port inside the container. `client_max_body_size 50m;` raises the maximum request size so a push of a larger repository is not rejected. `location = /healthz` matches exactly that path and answers directly: `default_type text/plain;` sets the content type and `return 200 "ok\n";` sends the status and body, which the Docker health check relies on.

```nginx
    location ~ ^/.+\.git/(HEAD|info/refs|objects/info/.*|git-(upload|receive)-pack)$ {
      include /etc/nginx/fastcgi_params;
      fastcgi_pass unix:/tmp/fcgiwrap.sock;
      fastcgi_param SCRIPT_FILENAME /usr/libexec/git-core/git-http-backend;
      fastcgi_param GIT_PROJECT_ROOT /srv/git;
      fastcgi_param GIT_HTTP_EXPORT_ALL "";
      fastcgi_param PATH_INFO $uri;
      fastcgi_param REMOTE_USER local;
    }
  }
}
```
The second `location` uses `~`, which means "the path matches this regular expression". The pattern `^/.+\.git/(HEAD|info/refs|objects/info/.*|git-(upload|receive)-pack)$` accepts a repository path ending in `.git/` followed by one of the files a Git client asks for: `HEAD`, the reference list `info/refs`, `objects/info/...`, or the two service endpoints `git-upload-pack` (used by fetch and clone) and `git-receive-pack` (used by push). Anything else gets no match. Inside: `include /etc/nginx/fastcgi_params;` loads the standard CGI variables; `fastcgi_pass unix:/tmp/fcgiwrap.sock;` forwards the request to the `fcgiwrap` socket; `SCRIPT_FILENAME` names the program to run; `GIT_PROJECT_ROOT /srv/git` is where the bare repositories live; `GIT_HTTP_EXPORT_ALL ""` allows serving every repository without a marker file; `PATH_INFO $uri` passes the request path; `REMOTE_USER local` marks the request as coming from a user named `local` (git refuses pushes with no user name). The last two lines close the `server` and `http` blocks.
<!-- full-walkthrough:end -->

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
