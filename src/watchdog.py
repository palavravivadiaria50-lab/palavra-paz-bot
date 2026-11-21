"""Watchdog / Health Check diário autônomo do Palavra & Paz (@palavraepaz.oficial)."""

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
LABEL_NAME = "alerta-automacao"

TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "curl exit 28",
    "500",
    "502",
    "503",
    "504",
    "unavailable",
    "temporarily",
    "econnreset",
    "connection reset",
    "ssl",
    "rate limit",
    "9007",
    "2207027",
    "is_transient",
    "not ready to be published",
    "aguarde um momento",
)


def _curl_bin() -> str:
    return shutil.which("curl.exe") or shutil.which("curl") or "curl"


def _curl_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
    timeout: int = 30,
) -> tuple[int, str]:
    """Executa requisição HTTP via curl nativo e retorna (status_code, body)."""
    marker = "__HTTP_STATUS__:"
    cmd = [_curl_bin(), "-s", "-L", "--max-time", str(timeout), "-X", method]
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])

    temp_body_file = None
    if json_body is not None:
        temp_dir = BASE_DIR / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_body_file = temp_dir / "watchdog_req.json"
        temp_body_file.write_text(json.dumps(json_body, ensure_ascii=False), encoding="utf-8")
        cmd.extend(["-H", "Content-Type: application/json", "-d", f"@{temp_body_file.resolve()}"])

    cmd.extend(["-w", f"\n{marker}%{{http_code}}", url])
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    finally:
        if temp_body_file and temp_body_file.exists():
            temp_body_file.unlink()

    out = res.stdout or ""
    if marker in out:
        body, status_str = out.rsplit(marker, 1)
        try:
            code = int(status_str.strip())
        except ValueError:
            code = 0
        return code, body.strip()
    return 0, out.strip()


def _gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "palavra-paz-watchdog",
    }


def check_github_workflows(repo: str, gh_token: str) -> tuple[list[str], list[str]]:
    """Verifica runs das últimas 24h, tenta 1 re-run em erros transitórios e retorna (infos, criticos)."""
    infos: list[str] = []
    criticos: list[str] = []
    if not repo or not gh_token:
        infos.append("GITHUB_TOKEN ou GITHUB_REPO ausente; verificação de workflows ignorada.")
        return infos, criticos

    headers = _gh_headers(gh_token)
    code, body = _curl_request(
        f"https://api.github.com/repos/{repo}/actions/runs?per_page=30",
        headers=headers,
    )
    if code != 200:
        criticos.append(f"Falha ao consultar GitHub Actions API (HTTP {code}): {body[:200]}")
        return infos, criticos

    runs = json.loads(body).get("workflow_runs", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    status_file = BASE_DIR / "data" / "status_publicacoes.json"
    try:
        st_data = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}
    except Exception:
        st_data = {}
    already_rerun_ids: set[str] = set(str(x) for x in st_data.get("watchdog_reruns", []))

    for run in runs:
        if "watchdog" in (run.get("path") or "").lower():
            continue
        if run.get("status") != "completed":
            continue
        created_str = run.get("created_at", "")
        if not created_str:
            continue
        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        if created_dt < cutoff:
            continue

        if run.get("conclusion") != "failure":
            continue

        run_id = run["id"]
        name = run.get("name", "workflow")
        attempt = int(run.get("run_attempt", 1))
        html_url = run.get("html_url", "")

        # Lê jobs e log do job que falhou
        _, jobs_body = _curl_request(
            f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs",
            headers=headers,
        )
        error_excerpt = "Sem detalhe de log."
        try:
            jobs = json.loads(jobs_body).get("jobs", [])
            failed_job = next((j for j in jobs if j.get("conclusion") == "failure"), None)
            if failed_job:
                _, log_txt = _curl_request(
                    f"https://api.github.com/repos/{repo}/actions/jobs/{failed_job['id']}/logs",
                    headers=headers,
                    timeout=30,
                )
                tail_lines = [ln for ln in log_txt.splitlines() if ln.strip()][-15:]
                error_excerpt = "\n".join(tail_lines)[-700:]
        except Exception:
            pass

        lower_err = error_excerpt.lower()
        is_transient = any(m in lower_err for m in TRANSIENT_MARKERS)
        fb_already_ok = (
            "[facebook feed] publicado" in lower_err
            or "[facebook carrossel] publicado" in lower_err
            or "[facebook story] publicado" in lower_err
        )
        fb_note = (
            " (Facebook já publicado na tentativa anterior; anti-duplicidade ativo)"
            if fb_already_ok
            else ""
        )

        if is_transient and attempt == 1 and str(run_id) not in already_rerun_ids:
            rr_code, _ = _curl_request(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs",
                method="POST",
                headers=headers,
            )
            if rr_code in (200, 201):
                already_rerun_ids.add(str(run_id))
                st_data["watchdog_reruns"] = sorted(already_rerun_ids)
                status_file.parent.mkdir(parents=True, exist_ok=True)
                status_file.write_text(
                    json.dumps(st_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                infos.append(
                    f"Re-run disparado automaticamente para '{name}' (run {run_id}, tentativa 1 -> 2, erro transitório){fb_note}."
                )
                continue

        criticos.append(
            f"Falha no workflow **{name}** (`run_id={run_id}`, tentativa `{attempt}`, criado em `{created_str}`){fb_note}:\n"
            f"- Link: {html_url}\n"
            f"- Trecho do erro:\n```text\n{error_excerpt}\n```"
        )

    if not infos and not criticos:
        infos.append("Todos os workflows das últimas 24h executaram sem falhas.")
    return infos, criticos


def check_apis() -> tuple[list[str], list[str]]:
    """Valida META_ACCESS_TOKEN, PIXABAY_API_KEY e GEMINI_API_KEY."""
    infos: list[str] = []
    criticos: list[str] = []

    # 1. Meta Graph API
    meta_token = os.getenv("META_ACCESS_TOKEN", "").strip()
    ig_id = os.getenv("IG_USER_ID", "").strip()
    if not meta_token:
        criticos.append("`META_ACCESS_TOKEN` não configurado.")
    else:
        code, body = _curl_request(
            f"https://graph.facebook.com/v21.0/me?fields=id,name&access_token={meta_token}"
        )
        if code != 200 or '"error"' in body:
            criticos.append(f"Token da Meta inválido ou expirado (HTTP {code}): {body[:300]}")
        else:
            infos.append("Meta Graph API (`/me`) válida.")

        if ig_id:
            ig_code, ig_body = _curl_request(
                f"https://graph.facebook.com/v21.0/{ig_id}?fields=id,username&access_token={meta_token}"
            )
            if ig_code != 200 or '"error"' in ig_body:
                criticos.append(f"Conta Instagram (`{ig_id}`) inacessível (HTTP {ig_code}): {ig_body[:300]}")
            else:
                infos.append("Instagram Business API válida.")

    # 2. Pixabay API
    px_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not px_key:
        criticos.append("`PIXABAY_API_KEY` não configurada.")
    else:
        code, body = _curl_request(
            f"https://pixabay.com/api/?key={px_key}&q=sky&per_page=3"
        )
        if code != 200 or '"hits"' not in body:
            criticos.append(f"Pixabay API falhou (HTTP {code}): {body[:200]}")
        else:
            infos.append("Pixabay API válida.")

    # 3. Gemini API
    gm_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gm_key:
        criticos.append("`GEMINI_API_KEY` não configurada.")
    else:
        code, body = _curl_request(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={gm_key}"
        )
        if code != 200 or '"models"' not in body:
            criticos.append(f"Gemini API falhou (HTTP {code}): {body[:200]}")
        else:
            infos.append("Gemini API válida.")

    return infos, criticos


def check_vitrine() -> tuple[list[str], list[str]]:
    """Verifica status 200 em palavraepaz.netlify.app e links de afiliados sem 404."""
    infos: list[str] = []
    criticos: list[str] = []
    base_url = "https://palavraepaz.netlify.app"

    code, _ = _curl_request(base_url, timeout=20)
    if code != 200:
        criticos.append(f"Vitrine `{base_url}` retornou HTTP {code} (esperado 200).")
        return infos, criticos
    infos.append(f"Vitrine `{base_url}` online (HTTP 200).")

    l_code, l_body = _curl_request(f"{base_url}/links.json", timeout=20)
    if l_code != 200:
        local_links = BASE_DIR / "links" / "links.json"
        if local_links.exists():
            items = json.loads(local_links.read_text(encoding="utf-8"))
        else:
            criticos.append(f"Falha ao carregar `links.json` da vitrine (HTTP {l_code}).")
            return infos, criticos
    else:
        items = json.loads(l_body)

    ua_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for item in items:
        url = item.get("url", "")
        titulo = item.get("titulo", url)
        if not url:
            continue
        u_code, _ = _curl_request(url, headers=ua_headers, timeout=20)
        if u_code == 404 or u_code == 0 or u_code >= 500:
            criticos.append(f"Link fora do ar na vitrine (**{titulo}**): `{url}` retornou HTTP {u_code}.")
        else:
            infos.append(f"Link OK ({u_code}): {titulo}")

    return infos, criticos


def sync_github_issue(repo: str, gh_token: str, criticos: list[str], infos: list[str]) -> None:
    """Abre/atualiza issue de alerta se houver falhas críticas; fecha antigas se tudo estiver OK."""
    if not repo or not gh_token:
        print("[Watchdog] Sem GITHUB_TOKEN/GITHUB_REPO para gerenciar Issues.")
        return

    headers = _gh_headers(gh_token)
    # Garante existência do rótulo alerta-automacao
    _curl_request(
        f"https://api.github.com/repos/{repo}/labels",
        method="POST",
        headers=headers,
        json_body={
            "name": LABEL_NAME,
            "color": "d73a4a",
            "description": "Alertas automáticos do Watchdog Palavra & Paz",
        },
    )

    _, issues_body = _curl_request(
        f"https://api.github.com/repos/{repo}/issues?state=open&labels={LABEL_NAME}",
        headers=headers,
    )
    open_issues = json.loads(issues_body) if issues_body.startswith("[") else []

    now_brt = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M BRT")

    if criticos:
        body_md = (
            f"## Alerta Automático do Watchdog (`{now_brt}`)\n\n"
            "Foram detectados problemas que precisam de atenção:\n\n"
            + "\n\n".join(f"- {c}" for c in criticos)
            + "\n\n---\n### Verificações OK\n"
            + "\n".join(f"- {i}" for i in infos)
        )
        title = f"[Watchdog] Alerta de Automação — {now_brt}"
        if open_issues:
            num = open_issues[0]["number"]
            _curl_request(
                f"https://api.github.com/repos/{repo}/issues/{num}",
                method="PATCH",
                headers=headers,
                json_body={"title": title, "body": body_md},
            )
            print(f"[Watchdog] Issue #{num} atualizada com novos detalhes.")
        else:
            c_code, c_body = _curl_request(
                f"https://api.github.com/repos/{repo}/issues",
                method="POST",
                headers=headers,
                json_body={"title": title, "body": body_md, "labels": [LABEL_NAME]},
            )
            print(f"[Watchdog] Nova Issue criada (HTTP {c_code}): {c_body[:120]}")
    else:
        for iss in open_issues:
            num = iss["number"]
            _curl_request(
                f"https://api.github.com/repos/{repo}/issues/{num}/comments",
                method="POST",
                headers=headers,
                json_body={"body": f"Resolvido automaticamente em `{now_brt}`. Todas as verificações passaram 100%."},
            )
            _curl_request(
                f"https://api.github.com/repos/{repo}/issues/{num}",
                method="PATCH",
                headers=headers,
                json_body={"state": "closed"},
            )
            print(f"[Watchdog] Issue #{num} fechada automaticamente (sistema 100% saudável).")


def cleanup_old_media() -> tuple[list[str], list[str]]:
    """Limpeza diária automática: limpa temp/ e mantém no máximo 5 arquivos (<= 2 dias) em output/."""
    infos: list[str] = []
    criticos: list[str] = []
    freed_bytes = 0
    removed = 0

    # 1. Remove temporários soltos
    for folder_name in ("temp", "tmp", "cache", "downloads"):
        folder = BASE_DIR / folder_name
        if not folder.exists():
            continue
        for f in list(folder.rglob("*")):
            if f.is_file():
                try:
                    freed_bytes += f.stat().st_size
                    os.remove(f)
                    removed += 1
                except OSError:
                    pass

    # 2. Retenção na pasta output/: mantém no máximo os 5 mais recentes e remove > 2 dias
    out_dir = BASE_DIR / "output"
    if out_dir.exists():
        cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
        all_files = sorted(
            [f for f in out_dir.rglob("*") if f.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for idx, f in enumerate(all_files):
            if idx >= 5 or f.stat().st_mtime < cutoff_ts:
                try:
                    freed_bytes += f.stat().st_size
                    os.remove(f)
                    removed += 1
                except OSError:
                    pass

    infos.append(
        f"Faxina automática concluída: {removed} arquivo(s) removido(s) ({freed_bytes / 1024 / 1024:.2f} MB liberados)."
    )
    return infos, criticos


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    repo = os.getenv("GITHUB_REPO", "palavravivadiaria50-lab/palavra-paz-bot").strip()
    gh_token = os.getenv("GITHUB_TOKEN", "").strip()

    print("=== [WATCHDOG] Iniciando Health Check Palavra & Paz ===")
    all_infos: list[str] = []
    all_criticos: list[str] = []

    for label, fn in (
        ("Workflows GitHub", lambda: check_github_workflows(repo, gh_token)),
        ("APIs & Tokens", check_apis),
        ("Vitrine Netlify", check_vitrine),
        ("Auto-Cleanup Mídia", cleanup_old_media),
    ):
        infos, criticos = fn()
        all_infos.extend(infos)
        all_criticos.extend(criticos)
        print(f"\n[{label}] OK={len(infos)} | CRITICOS={len(criticos)}")
        for i in infos:
            print(f"  [OK] {i}")
        for c in criticos:
            print(f"  [ALERTA] {c}")

    sync_github_issue(repo, gh_token, all_criticos, all_infos)
    print("\n=== [WATCHDOG] Finalizado ===")


if __name__ == "__main__":
    main()
