"""Publicador Meta Graph API v21.0 via curl.exe com retry progressivo (9007/2207027) e anti-duplicidade."""

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


GRAPH_BASE = "https://graph.facebook.com/v21.0"
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_PATH = BASE_DIR / "data" / "status_publicacoes.json"
RETRY_WAIT_SECONDS = (10, 15, 20)


def _is_transient_meta_error(err: dict) -> bool:
    """Identifica erro transitório da Meta (ex: code 9007, subcode 2207027, is_transient=True)."""
    if not isinstance(err, dict):
        return False
    if err.get("is_transient") is True:
        return True
    if err.get("code") in (9007, 1, 2, 4, 17):
        return True
    if err.get("error_subcode") in (2207027, 2207052):
        return True
    msg = str(err.get("message", "")).lower()
    return "not ready" in msg or "aguarde um momento" in msg or "please wait" in msg


def _curl_json(curl_args: list[str], max_attempts: int = 4) -> dict:
    """Executa curl.exe com timeout de 30s e retry progressivo (10s, 15s, 20s) em erros transitórios."""
    cmd = ["curl.exe", "-s", "--max-time", "30", *curl_args]
    last_err = None

    for attempt in range(max_attempts):
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        raw = res.stdout.strip()
        if not raw:
            last_err = "Resposta vazia da Meta Graph API."
            if attempt < max_attempts - 1:
                wait_s = RETRY_WAIT_SECONDS[min(attempt, len(RETRY_WAIT_SECONDS) - 1)]
                print(f"[Meta Retry {attempt + 1}/{max_attempts}] Resposta vazia, aguardando {wait_s}s...")
                time.sleep(wait_s)
                continue
            raise RuntimeError(last_err)

        data = json.loads(raw)
        if "error" in data:
            err = data["error"]
            if _is_transient_meta_error(err) and attempt < max_attempts - 1:
                wait_s = RETRY_WAIT_SECONDS[min(attempt, len(RETRY_WAIT_SECONDS) - 1)]
                print(
                    f"[Meta Retry {attempt + 1}/{max_attempts}] Erro transitório "
                    f"(code={err.get('code')}, subcode={err.get('error_subcode')}), "
                    f"aguardando {wait_s}s antes de tentar novamente..."
                )
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"Erro Meta API: {err}")

        return data

    raise RuntimeError(f"Falha após {max_attempts} tentativas na Meta API: {last_err}")


def _load_status() -> dict:
    if STATUS_PATH.exists():
        try:
            return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_status(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _post_key(kind: str, identifier: str) -> str:
    today_brt = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")
    digest = hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:10]
    return f"{today_brt}_{kind}_{digest}"


def _get_done(key: str, channel: str) -> str | None:
    return _load_status().get(key, {}).get(channel)


def _mark_done(key: str, channel: str, post_id: str) -> None:
    st = _load_status()
    st.setdefault(key, {})[channel] = str(post_id)
    _save_status(st)


def _get_meta_creds() -> tuple[str, str, str]:
    page_id = os.getenv("FB_PAGE_ID", "").strip()
    ig_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not page_id or not ig_id or not token:
        raise ValueError(
            "FB_PAGE_ID, IG_USER_ID ou META_ACCESS_TOKEN não configurados no .env."
        )
    return page_id, ig_id, token


def _upload_hidden_fb_photo(image_path: Path, page_id: str, token: str) -> tuple[str, str]:
    """Upload oculto (published=false) no FB e leitura da URL CDN pública."""
    up_data = _curl_json(
        [
            "-X",
            "POST",
            f"{GRAPH_BASE}/{page_id}/photos",
            "-F",
            "published=false",
            "-F",
            f"source=@{image_path.resolve()}",
            "-F",
            f"access_token={token}",
        ]
    )
    photo_id = up_data["id"]

    info_data = _curl_json(
        [
            "-G",
            f"{GRAPH_BASE}/{photo_id}",
            "--data-urlencode",
            "fields=images",
            "--data-urlencode",
            f"access_token={token}",
        ]
    )
    images = info_data.get("images", [])
    if not images:
        raise RuntimeError(f"Meta não retornou URL CDN para photo_id={photo_id}")
    return photo_id, images[0]["source"]


def _delete_fb_photo(photo_id: str, token: str) -> None:
    try:
        _curl_json(
            [
                "-X",
                "DELETE",
                f"{GRAPH_BASE}/{photo_id}",
                "-d",
                f"access_token={token}",
            ],
            max_attempts=1,
        )
    except Exception:
        pass


def _wait_ig_container_finished(creation_id: str, token: str, timeout_s: int = 60) -> None:
    """Aguarda status_code == FINISHED no container do Instagram + pausa de estabilização."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status_data = _curl_json(
            [
                "-G",
                f"{GRAPH_BASE}/{creation_id}",
                "--data-urlencode",
                "fields=status_code",
                "--data-urlencode",
                f"access_token={token}",
            ]
        )
        code = status_data.get("status_code", "")
        if code == "FINISHED":
            time.sleep(4)
            return
        if code == "ERROR":
            raise RuntimeError(f"Container IG {creation_id} retornou status ERROR: {status_data}")
        time.sleep(4)
    raise TimeoutError(f"Container IG {creation_id} não atingiu FINISHED em {timeout_s}s.")


def publish_single_post(image_path: Path, caption: str) -> dict:
    """Publica card único no Feed do Facebook e no Feed do Instagram (sem duplicar em re-run)."""
    page_id, ig_id, token = _get_meta_creds()
    key = _post_key("single", caption[:120])

    # 1. Facebook Feed
    existing_fb = _get_done(key, "fb_feed")
    if existing_fb:
        print(f"[Facebook Feed] Já publicado hoje (ID: {existing_fb}), pulando para evitar duplicidade.")
        fb_data = {"id": existing_fb, "skipped_duplicate": True}
    else:
        fb_data = _curl_json(
            [
                "-X",
                "POST",
                f"{GRAPH_BASE}/{page_id}/photos",
                "-F",
                f"source=@{image_path.resolve()}",
                "-F",
                f"caption={caption}",
                "-F",
                f"access_token={token}",
            ]
        )
        _mark_done(key, "fb_feed", fb_data.get("id", "ok"))
        print(f"[Facebook Feed] Publicado! ID: {fb_data.get('id')}")

    # 2. Instagram Feed
    existing_ig = _get_done(key, "ig_feed")
    if existing_ig:
        print(f"[Instagram Feed] Já publicado hoje (media_id: {existing_ig}), pulando.")
        ig_data = {"id": existing_ig, "skipped_duplicate": True}
    else:
        photo_id, cdn_url = _upload_hidden_fb_photo(image_path, page_id, token)
        try:
            c_data = _curl_json(
                [
                    "-X",
                    "POST",
                    f"{GRAPH_BASE}/{ig_id}/media",
                    "--data-urlencode",
                    f"image_url={cdn_url}",
                    "--data-urlencode",
                    f"caption={caption}",
                    "--data-urlencode",
                    f"access_token={token}",
                ]
            )
            creation_id = c_data["id"]
            _wait_ig_container_finished(creation_id, token)
            ig_data = _curl_json(
                [
                    "-X",
                    "POST",
                    f"{GRAPH_BASE}/{ig_id}/media_publish",
                    "--data-urlencode",
                    f"creation_id={creation_id}",
                    "--data-urlencode",
                    f"access_token={token}",
                ]
            )
            _mark_done(key, "ig_feed", ig_data.get("id", "ok"))
            print(f"[Instagram Feed] Publicado! media_id: {ig_data.get('id')}")
        finally:
            _delete_fb_photo(photo_id, token)

    return {"facebook": fb_data, "instagram": ig_data}


def publish_carousel(image_paths: list[Path], caption: str) -> dict:
    """Publica carrossel de 3 slides no Feed do Instagram e multi-foto no Feed do Facebook."""
    page_id, ig_id, token = _get_meta_creds()
    key = _post_key("carousel", caption[:120])

    # 1. Facebook Carrossel
    existing_fb = _get_done(key, "fb_carousel")
    if existing_fb:
        print(f"[Facebook Carrossel] Já publicado hoje (post_id: {existing_fb}), pulando para evitar duplicidade.")
        fb_data = {"id": existing_fb, "skipped_duplicate": True}
    else:
        fb_uploads: list[tuple[str, str]] = [
            _upload_hidden_fb_photo(p, page_id, token) for p in image_paths
        ]
        fb_args = [
            "-X",
            "POST",
            f"{GRAPH_BASE}/{page_id}/feed",
            "--data-urlencode",
            f"message={caption}",
            "--data-urlencode",
            f"access_token={token}",
        ]
        for idx, (pid, _) in enumerate(fb_uploads):
            fb_args.extend(
                ["--data-urlencode", f"attached_media[{idx}]={json.dumps({'media_fbid': pid})}"]
            )
        fb_data = _curl_json(fb_args)
        _mark_done(key, "fb_carousel", fb_data.get("id", "ok"))
        print(f"[Facebook Carrossel] Publicado! post_id: {fb_data.get('id')}")

    # 2. Instagram Carrossel
    existing_ig = _get_done(key, "ig_carousel")
    if existing_ig:
        print(f"[Instagram Carrossel] Já publicado hoje (media_id: {existing_ig}), pulando.")
        ig_data = {"id": existing_ig, "skipped_duplicate": True}
    else:
        ig_temp_uploads = [_upload_hidden_fb_photo(p, page_id, token) for p in image_paths]
        try:
            child_ids: list[str] = []
            for _, cdn_url in ig_temp_uploads:
                item_data = _curl_json(
                    [
                        "-X",
                        "POST",
                        f"{GRAPH_BASE}/{ig_id}/media",
                        "--data-urlencode",
                        f"image_url={cdn_url}",
                        "--data-urlencode",
                        "is_carousel_item=true",
                        "--data-urlencode",
                        f"access_token={token}",
                    ]
                )
                _wait_ig_container_finished(item_data["id"], token)
                child_ids.append(item_data["id"])

            parent_data = _curl_json(
                [
                    "-X",
                    "POST",
                    f"{GRAPH_BASE}/{ig_id}/media",
                    "--data-urlencode",
                    "media_type=CAROUSEL",
                    "--data-urlencode",
                    f"children={','.join(child_ids)}",
                    "--data-urlencode",
                    f"caption={caption}",
                    "--data-urlencode",
                    f"access_token={token}",
                ]
            )
            parent_id = parent_data["id"]
            _wait_ig_container_finished(parent_id, token)

            ig_data = _curl_json(
                [
                    "-X",
                    "POST",
                    f"{GRAPH_BASE}/{ig_id}/media_publish",
                    "--data-urlencode",
                    f"creation_id={parent_id}",
                    "--data-urlencode",
                    f"access_token={token}",
                ]
            )
            _mark_done(key, "ig_carousel", ig_data.get("id", "ok"))
            print(f"[Instagram Carrossel] Publicado! media_id: {ig_data.get('id')}")
        finally:
            for pid, _ in ig_temp_uploads:
                _delete_fb_photo(pid, token)

    return {"facebook": fb_data, "instagram": ig_data}


def publish_story(image_path: Path) -> dict:
    """Publica Story no Facebook Page (/photo_stories) e no Instagram Business (STORIES)."""
    page_id, ig_id, token = _get_meta_creds()
    key = _post_key("story", image_path.name)

    # 1. Facebook Story
    existing_fb = _get_done(key, "fb_story")
    if existing_fb:
        print(f"[Facebook Story] Já publicado hoje (ID: {existing_fb}), pulando para evitar duplicidade.")
        fb_story = {"id": existing_fb, "skipped_duplicate": True}
    else:
        fb_photo_id, _ = _upload_hidden_fb_photo(image_path, page_id, token)
        fb_story = _curl_json(
            [
                "-X",
                "POST",
                f"{GRAPH_BASE}/{page_id}/photo_stories",
                "--data-urlencode",
                f"photo_id={fb_photo_id}",
                "--data-urlencode",
                f"access_token={token}",
            ]
        )
        sid = fb_story.get("post_id") or fb_story.get("id") or "ok"
        _mark_done(key, "fb_story", sid)
        print(f"[Facebook Story] Publicado! ID: {sid}")

    # 2. Instagram Story
    existing_ig = _get_done(key, "ig_story")
    if existing_ig:
        print(f"[Instagram Story] Já publicado hoje (media_id: {existing_ig}), pulando.")
        ig_story = {"id": existing_ig, "skipped_duplicate": True}
    else:
        ig_temp_id, cdn_url = _upload_hidden_fb_photo(image_path, page_id, token)
        try:
            c_data = _curl_json(
                [
                    "-X",
                    "POST",
                    f"{GRAPH_BASE}/{ig_id}/media",
                    "--data-urlencode",
                    f"image_url={cdn_url}",
                    "--data-urlencode",
                    "media_type=STORIES",
                    "--data-urlencode",
                    f"access_token={token}",
                ]
            )
            creation_id = c_data["id"]
            _wait_ig_container_finished(creation_id, token)

            ig_story = _curl_json(
                [
                    "-X",
                    "POST",
                    f"{GRAPH_BASE}/{ig_id}/media_publish",
                    "--data-urlencode",
                    f"creation_id={creation_id}",
                    "--data-urlencode",
                    f"access_token={token}",
                ]
            )
            _mark_done(key, "ig_story", ig_story.get("id", "ok"))
            print(f"[Instagram Story] Publicado! media_id: {ig_story.get('id')}")
        finally:
            _delete_fb_photo(ig_temp_id, token)

    return {"facebook": fb_story, "instagram": ig_story}
