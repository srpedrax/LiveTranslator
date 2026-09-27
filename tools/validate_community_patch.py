#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import unicodedata
import urllib.request
import urllib.error

API = "https://api.github.com"
MAX_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 50000
ALLOWED_KEYS = {"modName", "modVersion", "language", "author", "entries"}

def fail(message):
    print(f"::error::{message}")
    raise SystemExit(1)

def api(path, token):
    req = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "LiveTranslator-CommunityValidator",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        fail(f"GitHub API HTTP {e.code}: {body[:400]}")

def safe_segment(value, fallback="unknown"):
    value = unicodedata.normalize("NFKD", str(value or fallback))
    value = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE)
    value = value.strip("-")[:80]
    return value or fallback

def find_pr(repo, token, pr_number, expected_sha):
    if pr_number:
        return api(f"/repos/{repo}/pulls/{pr_number}", token)

    pulls = api(f"/repos/{repo}/pulls?state=open&per_page=100", token)
    matches = [p for p in pulls if p.get("head", {}).get("sha") == expected_sha]
    if len(matches) != 1:
        fail(f"Não consegui associar o workflow a um único PR (matches={len(matches)}).")
    return matches[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", type=int)
    ap.add_argument("--expected-sha")
    ap.add_argument("--result", default="validation-result.json")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN")
    if not token:
        fail("GH_TOKEN ausente.")

    pr = find_pr(args.repo, token, args.pr, args.expected_sha)
    pr_number = pr["number"]
    head_sha = pr["head"]["sha"]
    head_repo = pr["head"]["repo"]["full_name"]
    author = pr["user"]["login"]

    if args.expected_sha and head_sha != args.expected_sha:
        fail("O PR mudou depois da execução de validação. Novo commit precisa ser validado.")

    files = api(f"/repos/{args.repo}/pulls/{pr_number}/files?per_page=100", token)
    if len(files) != 1:
        fail("Cada envio comunitário deve alterar exatamente um arquivo JSON.")

    f = files[0]
    filename = f["filename"]
    status = f["status"]

    if status not in ("added", "modified"):
        fail(f"Operação de arquivo não permitida: {status}.")

    if not filename.lower().endswith(".json"):
        fail("Somente arquivos .json são aceitos.")

    parts = filename.split("/")
    # Novo formato:
    # packs/<language>/<modName>/<github-user>/<arquivo>.json
    # Formato legado de teste (somente dono do repo):
    # packs/<language>/<modName>/<arquivo>.json
    if len(parts) == 5 and parts[0] == "packs":
        _, path_language, path_mod, path_author, _ = parts
        if safe_segment(author).lower() != path_author.lower():
            fail("A pasta do contribuidor precisa corresponder ao usuário GitHub do PR.")
    elif len(parts) == 4 and parts[0] == "packs":
        _, path_language, path_mod, _ = parts
        repo_owner = args.repo.split("/", 1)[0]
        if author.lower() != repo_owner.lower():
            fail("Contribuidores externos precisam usar packs/idioma/mod/usuario/arquivo.json.")
    else:
        fail("Caminho inválido. Use packs/<idioma>/<mod>/<usuario>/<arquivo>.json.")

    blob_sha = f.get("sha")
    if not blob_sha:
        fail("SHA do arquivo não encontrado.")

    blob = api(f"/repos/{head_repo}/git/blobs/{blob_sha}", token)
    if blob.get("encoding") != "base64":
        fail("Encoding inesperado no blob do GitHub.")

    raw = base64.b64decode(blob["content"])
    if len(raw) > MAX_BYTES:
        fail("Patch maior que 2 MB.")

    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except Exception as e:
        fail(f"JSON inválido: {e}")

    if not isinstance(doc, dict):
        fail("A raiz do JSON precisa ser um objeto.")

    unknown = set(doc) - ALLOWED_KEYS
    if unknown:
        fail("Campos desconhecidos: " + ", ".join(sorted(unknown)))

    mod_name = doc.get("modName")
    language = doc.get("language")
    entries = doc.get("entries")

    if not isinstance(mod_name, str) or not mod_name.strip():
        fail("modName ausente ou inválido.")
    if not isinstance(language, str) or not language.strip():
        fail("language ausente ou inválido.")
    if not isinstance(entries, dict) or not entries:
        fail("entries precisa ser um objeto não vazio.")

    if safe_segment(mod_name).lower() != path_mod.lower():
        fail("modName do JSON não corresponde à pasta do mod.")
    if safe_segment(language).lower() != path_language.lower():
        fail("language do JSON não corresponde à pasta do idioma.")

    if len(entries) > MAX_ENTRIES:
        fail(f"Patch possui entradas demais ({len(entries)} > {MAX_ENTRIES}).")

    for i, (source, translated) in enumerate(entries.items(), 1):
        if not isinstance(source, str) or not source.strip():
            fail(f"Entrada #{i}: source vazio/inválido.")
        if not isinstance(translated, str) or not translated.strip():
            fail(f"Entrada #{i}: tradução vazia/inválida.")
        if "\x00" in source or "\x00" in translated:
            fail(f"Entrada #{i}: caractere NUL não permitido.")
        if len(source) > 20000 or len(translated) > 20000:
            fail(f"Entrada #{i}: texto individual grande demais.")

    result = {
        "ok": True,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "author": author,
        "filename": filename,
        "modName": mod_name,
        "language": language,
        "entries": len(entries),
    }

    with open(args.result, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)

    print(
        f"OK: PR #{pr_number} • {mod_name} • {language} • "
        f"{len(entries)} entradas • @{author}"
    )

if __name__ == "__main__":
    main()
