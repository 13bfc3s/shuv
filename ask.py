#!/usr/bin/env python3
"""Shuv approval for GitHub Actions: asks on the phone, waits, and passes or fails the step by the answer.

Inputs arrive as SHUV_* environment variables (see action.yml); the key is never printed. Python 3 standard
library only, so it runs on any GitHub-hosted or self-hosted runner with python3.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


def env(name, default=""):
    return os.environ.get(name, default).strip()


def seconds(text):
    m = re.fullmatch(r"(\d+)\s*([smhd]?)", text)
    if not m:
        raise SystemExit(f"::error::timeout must look like 30m, 2h or 1d, not {text!r}")
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def call(method, url, key, body=None, headers=None):
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"authorization": f"Bearer {key}", "content-type": "application/json",
                                          "user-agent": "shuv-github-action/1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError):
        return 0, {}


def output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}<<SHUV_EOF\n{value}\nSHUV_EOF\n")


def message(data):
    return (data.get("error") or {}).get("message") or "no details"


def main():
    key, api = env("SHUV_KEY"), env("SHUV_API", "https://shuv.cloud").rstrip("/")
    if not key:
        raise SystemExit("::error::Set the key input from a secret, e.g. key: ${{ secrets.SHUV_KEY }}")
    print(f"::add-mask::{key}")
    options = [o.strip() for o in env("SHUV_OPTIONS", "Approve,Reject").split(",") if o.strip()]
    passing = {o.strip().lower() for o in (env("SHUV_PASS_ON") or options[0]).split(",") if o.strip()}
    timeout = seconds(env("SHUV_TIMEOUT", "30m"))
    repo, run = env("GITHUB_REPOSITORY"), env("GITHUB_RUN_ID")
    link = f"{env('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{run}" if repo and run else ""
    details = env("SHUV_DETAILS") or "\n".join(x for x in [f"{repo} @ {env('GITHUB_REF_NAME')}", env("GITHUB_WORKFLOW"),
                                                           f"by {env('GITHUB_ACTOR')}" if env("GITHUB_ACTOR") else "", link] if x)
    body = {"title": env("SHUV_QUESTION")[:120], "body": details[:4000], "options": options, "expiresIn": timeout}
    if env("SHUV_DEFAULT"):
        body["onTimeout"] = env("SHUV_DEFAULT")
    if env("SHUV_TEAM").lower() == "true":
        body["to"] = "team"
    if env("SHUV_ESCALATE"):
        body["escalate"] = {"after": seconds(env("SHUV_ESCALATE"))}
    # Re-running the same attempt reuses the question instead of asking twice.
    idem = "gha-" + hashlib.sha256("|".join([repo, run, env("GITHUB_RUN_ATTEMPT"), env("GITHUB_JOB"), json.dumps(body, sort_keys=True)]).encode()).hexdigest()[:40]
    status, data = call("POST", f"{api}/v1/shuvs", key, body, {"idempotency-key": idem})
    if status not in (200, 201):
        raise SystemExit(f"::error::Shuv couldn't send the question (HTTP {status}: {message(data)})")
    shuv_id = data["data"]["id"]
    print(f"Asked on your phone: {body['title']} ({', '.join(options)}). Waiting up to {timeout} s.")
    deadline = time.time() + timeout + 60
    while time.time() < deadline:
        status, data = call("GET", f"{api}/v1/shuvs/{shuv_id}/response?wait=25", key)
        if status == 200:
            reply = data["data"]
            answer = reply.get("choice") or reply.get("message") or ""
            output("answer", answer)
            output("answered-by", reply.get("answeredBy", ""))
            output("timed-out", "true" if reply.get("timedOut") else "false")
            who = f" by {reply['answeredBy']}" if reply.get("answeredBy") else ""
            how = " (nobody answered; default used)" if reply.get("timedOut") else ""
            print(f"Answer: {answer}{who}{how}")
            if answer.lower() not in passing:
                raise SystemExit(f"::error::Not approved: {answer}{who}{how}")
            return
        if status == 410:
            output("timed-out", "true")
            raise SystemExit("::error::Nobody answered before the deadline.")
        if status in (401, 403, 404, 409, 422):
            raise SystemExit(f"::error::Shuv refused the request (HTTP {status}: {message(data)})")
        if status != 202:
            time.sleep(5)  # network trouble or 429/5xx: try again shortly
    raise SystemExit("::error::Gave up waiting for an answer.")


if __name__ == "__main__":
    main()
