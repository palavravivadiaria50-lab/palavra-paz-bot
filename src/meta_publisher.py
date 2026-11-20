"""Publicador Meta Graph API v21.0 via curl.exe (Feed Único, Carrossel 3 slides e Stories)."""

import json
import os
import subprocess
import time
from pathlib import Path


GRAPH_BASE = "https://graph.facebook.com/v21.0"


def _curl_json(curl_args: list[str]) -> dict:
    """Executa curl.exe com timeout de 30s e retorna JSON validado."""
    cmd = ["curl.exe", "-s", "--max-time", "30", *curl_args]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    raw = res.stdout.strip()
    if not raw:
        raise RuntimeError("Resposta vazia da Meta Graph API.")
    data = json.loads(raw)
    if "error" in data:
        raise RuntimeError(f"Erro Meta API: {data['error']}")
    return data


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
            ]
        )
    except Exception:
        pass


def _wait_ig_container_finished(creation_id: str, token: str, timeout_s: int = 45) -> None:
    """Aguarda status_code == FINISHED no container do Instagram."""
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
            return
        if code == "ERROR":
            raise RuntimeError(f"Container IG {creation_id} retornou status ERROR: {status_data}")
        time.sleep(3)
    raise TimeoutError(f"Container IG {creation_id} não atingiu FINISHED em {timeout_s}s.")


def publish_single_post(image_path: Path, caption: str) -> dict:
    """Publica card único no Feed do Facebook e no Feed do Instagram."""
    page_id, ig_id, token = _get_meta_creds()

    # 1. Facebook Feed (upload direto)
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
    print(f"[Facebook Feed] Publicado! ID: {fb_data.get('id')}")

    # 2. Instagram Feed (upload oculto FB -> CDN -> IG container -> publish -> cleanup)
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
        print(f"[Instagram Feed] Publicado! media_id: {ig_data.get('id')}")
    finally:
        _delete_fb_photo(photo_id, token)

    return {"facebook": fb_data, "instagram": ig_data}


def publish_carousel(image_paths: list[Path], caption: str) -> dict:
    """Publica carrossel de 3 slides no Feed do Instagram e multi-foto no Feed do Facebook."""
    page_id, ig_id, token = _get_meta_creds()

    # 1. Upload oculto dos 3 slides para obter photo_ids + URLs CDN
    fb_uploads: list[tuple[str, str]] = [
        _upload_hidden_fb_photo(p, page_id, token) for p in image_paths
    ]

    # 2. Facebook Feed multi-foto usando os photo_ids ocultos
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
    print(f"[Facebook Carrossel] Publicado! post_id: {fb_data.get('id')}")

    # 3. Instagram Carrossel (3 item containers -> parent CAROUSEL -> FINISHED -> publish)
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
        print(f"[Instagram Carrossel] Publicado! media_id: {ig_data.get('id')}")
    finally:
        for pid, _ in ig_temp_uploads:
            _delete_fb_photo(pid, token)

    return {"facebook": fb_data, "instagram": ig_data}


def publish_story(image_path: Path) -> dict:
    """Publica Story no Facebook Page (/photo_stories) e no Instagram Business (STORIES)."""
    page_id, ig_id, token = _get_meta_creds()

    # 1. Facebook Story (upload oculto -> /photo_stories)
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
    print(f"[Facebook Story] Publicado! ID: {fb_story.get('post_id') or fb_story.get('id')}")

    # 2. Instagram Story (upload oculto separado -> CDN -> STORIES -> FINISHED -> publish -> cleanup)
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
        print(f"[Instagram Story] Publicado! media_id: {ig_story.get('id')}")
    finally:
        _delete_fb_photo(ig_temp_id, token)

    return {"facebook": fb_story, "instagram": ig_story}
