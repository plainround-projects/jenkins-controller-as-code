# curl, sed, grep, openssl, tar and other command-line tools

## 1. What it is

Unix tools are small programs that each do one job and are joined with pipes. This note covers the ones this repository calls: `curl`, `sed`, `grep`, `openssl`, `tar`, `xargs`, `mktemp`, `base64`, `wc`, `tr`.

## 2. Why this repository uses it

The scripts talk to Jenkins and the store over HTTP, read XML attributes, pack a snapshot of the repository and generate secrets.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `pipeline/scripts/publish.sh` | `curl` with retries, a header from stdin and `--upload-file` |
| `scripts/lint-jenkinsfile.sh` | `curl` with cookies, a crumb and `--data-urlencode`; `sed -E` |
| `scripts/seed-project.sh` | `git ls-files -z | xargs -0 tar -cf - | tar -xf -`, `mktemp -d` |
| `scripts/init-env.sh` | `openssl rand -hex`, `sed -e`, `umask` |
| `agent/entrypoint.sh` | `curl -u`, `sed -n 's:...:p'`, `head -n 1` |
| `pipeline/scripts/test-summary.sh` | `grep -o`, `grep -m1` |

## 4. How it works underneath

- `curl -fsS`: `-f` fail on an HTTP error, `-s` silent, `-S` still show errors. `-u user:password` basic authentication; `-b/-c file` read/write a cookie file; `-H 'Name: value'` a header; `-X POST`; `--data-urlencode name@file` send a file's content as a form field; `--upload-file file` HTTP PUT; `--retry N` retry on failure.
- `sed -E 's/old/new/'` replaces (extended regex); `sed -n 's:a:b:p'` prints only lines where the replacement happened; any character can be the delimiter.
- `tar -cf - files | tar -xf - -C dir` copies files through a pipe.
- `xargs -0` reads NUL-separated names from standard input and passes them as arguments.
- `openssl rand -hex 16` prints 16 random bytes as 32 hex characters.
- `umask 077` makes files created afterwards readable only by their owner.

## 5. Walkthrough of this repository's use

```bash
(cd "${ROOT}" && git ls-files --cached --others --exclude-standard -z | xargs -0 tar -cf -) | tar -xf - -C "${snapshot}"
```
List the files Git tracks plus new unignored ones, NUL-separated (safe for names with spaces); `xargs -0` hands them to `tar -cf -` which writes an archive to standard output; the second `tar -xf -` unpacks it into the snapshot folder. The parentheses run the first part in a sub-shell so the `cd` does not affect the rest.

```bash
crumb="$(curl -fsS "${auth[@]}" "${CONTROLLER_URL}/crumbIssuer/api/json" | sed -E 's/.*"crumbRequestField":"([^"]+)".*"crumb":"([^"]+)".*/\1:\2/')"
```
Fetch Jenkins's CSRF crumb as JSON and rewrite the whole line into `FieldName:value`, the exact header syntax. `([^"]+)` captures everything up to the next quote; `\1` and `\2` put the captures back.

```bash
sed -n 's:.*<argument>\([0-9a-f]\{64\}\)</argument>.*:\1:p' | head -n 1
```
In the agent's entrypoint: print only the 64-hex-character value of an `<argument>` element (the agent secret) from the XML the controller returns. With `-n` only matching lines are printed (the `p` flag), and `head -n 1` keeps the first.

```bash
umask 077
sed -e "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$(openssl rand -hex 16)/" -e "..." .env.example > .env
```
Create `.env` readable only by its owner, with random secrets filled in.

## 6. Try it yourself

1. `curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18480/controller-as-code.git/info/refs?service=git-upload-pack` : `200` (stack up).
2. `echo '{"crumbRequestField":"Jenkins-Crumb","crumb":"abc"}' | sed -E 's/.*"crumbRequestField":"([^"]+)".*"crumb":"([^"]+)".*/\1:\2/'` : `Jenkins-Crumb:abc`.
3. `openssl rand -hex 16` : 32 hex characters.
4. `git ls-files -z | xargs -0 tar -cf - | tar -tf - | head -3` : the first archived files.
5. `echo '<argument>0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef</argument>' | sed -n 's:.*<argument>\([0-9a-f]\{64\}\)</argument>.*:\1:p'` : the 64 hex characters.

## 7. Mistakes people make

- Parsing JSON or XML with `sed` in general. The patterns here target tiny fixed shapes; a real parser is safer for anything bigger.
- Putting `-u user:password` on a command line: visible in `ps`. The publish script sends its token on standard input instead.
- Forgetting `-z`/`-0` and breaking on file names with spaces.

## 8. Check yourself

1. What does `curl -f` do?
   *Answer:* Fails with a non-zero status on an HTTP error.
2. Why `git ls-files -z | xargs -0`?
   *Answer:* NUL separators survive spaces in file names.
3. What does `sed -n '...p'` print?
   *Answer:* Only the lines where the substitution happened.
4. What does `umask 077` do?
   *Answer:* New files are readable only by their owner.
5. What is a crumb?
   *Answer:* Jenkins's CSRF token, sent in a header on POST requests.

## 9. Further reading

- curl man page: <https://curl.se/docs/manpage.html>. GNU tar: <https://www.gnu.org/software/tar/manual/>. GNU sed: <https://www.gnu.org/software/sed/manual/sed.html>. OpenSSL `rand`: <https://docs.openssl.org/master/man1/openssl-rand/>.
