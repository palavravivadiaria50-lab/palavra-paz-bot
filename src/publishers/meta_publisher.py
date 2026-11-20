"""Publicador Meta Graph API v21.0 usando curl.exe nativo do Windows (Schannel)."""

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


def publish_facebook_photo(image_path: Path, caption: str) -> dict:
    """Publica foto diretamente na Página do Facebook via multipart/form-data."""
    page_id = os.getenv("FB_PAGE_ID", "").strip()
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        raise ValueError("FB_PAGE_ID ou META_ACCESS_TOKEN não configurados no .env.")

    data = _curl_json(
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
    print(f"[Facebook] Publicado com sucesso! ID: {data.get('id')}")
    return data


def _upload_temp_fb_photo(image_path: Path, page_id: str, token: str) -> tuple[str, str]:
    """1) Upload oculto (published=false) e 2) leitura da URL CDN em fields=images."""
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


def _delete_temp_fb_photo(photo_id: str, token: str) -> None:
    """5) Remoção da foto temporária (DELETE /{photo_id})."""
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


def publish_instagram_photo(image_path: Path, caption: str) -> dict:
    """Publica foto no Instagram Business usando o fluxo nativo de 5 passos via curl.exe."""
    page_id = os.getenv("FB_PAGE_ID", "").strip()
    ig_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not page_id or not ig_id or not token:
        raise ValueError(
            "FB_PAGE_ID, IG_USER_ID ou META_ACCESS_TOKEN não configurados no .env."
        )

    photo_id, cdn_url = _upload_temp_fb_photo(image_path, page_id, token)
    try:
        # 3) Criação do container em /{IG_USER_ID}/media
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

        # 4) Espera de 5s e publicação em /{IG_USER_ID}/media_publish
        time.sleep(5)
        p_data = _curl_json(
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
        print(f"[Instagram] Publicado com sucesso! media_id: {p_data.get('id')}")
        return p_data
    finally:
        # 5) Remoção da foto temporária
        _delete_temp_fb_photo(photo_id, token)
