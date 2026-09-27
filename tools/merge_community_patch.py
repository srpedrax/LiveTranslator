#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request
import urllib.error

API = "https://api.github.com"

def request(method, path, token, body=None):
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "LiveTranslator-CommunityAutoPublish",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"message": raw}
        return e.code, payload

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--result", required=True)
    args = ap.parse_args()

    token = os.environ["GH_TOKEN"]
    with open(args.result, "r", encoding="utf-8") as fp:
        result = json.load(fp)

    pr_number = result["pr_number"]
    head_sha = result["head_sha"]

    status, pr = request("GET", f"/repos/{args.repo}/pulls/{pr_number}", token)
    if status != 200:
        raise SystemExit(f"Não consegui reler PR #{pr_number}: HTTP {status}")

    if pr["state"] != "open":
        raise SystemExit(f"PR #{pr_number} não está aberto.")
    if pr["head"]["sha"] != head_sha:
        raise SystemExit("PR mudou depois da validação segura. Não será publicado.")

    status, merged = request(
        "PUT",
        f"/repos/{args.repo}/pulls/{pr_number}/merge",
        token,
        {
            "sha": head_sha,
            "merge_method": "squash",
            "commit_title": f"community: publish patch from @{result['author']}",
            "commit_message":
                f"{result['modName']} • {result['language']} • "
                f"{result['entries']} entries",
        },
    )

    if status != 200 or not merged.get("merged"):
        message = merged.get("message", "merge recusado")
        raise SystemExit(f"Auto-publicação falhou: HTTP {status} • {message}")

    print(f"PUBLICADO: PR #{pr_number} foi integrado automaticamente.")

    # Branch direta no repo oficial: podemos remover a branch temporária.
    if pr["head"]["repo"]["full_name"].lower() == args.repo.lower():
        ref = pr["head"]["ref"]
        if ref.startswith("live-translator/"):
            status, _ = request(
                "DELETE",
                f"/repos/{args.repo}/git/refs/heads/{ref.replace('/', '%2F')}",
                token,
            )
            print(f"Limpeza da branch: HTTP {status}")

if __name__ == "__main__":
    main()
