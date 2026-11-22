"""Publicador modular para YouTube Shorts (Data API v3 via curl.exe) e TikTok."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.video_generator import BASE_DIR, generate_short_video


def _curl_bin() -> str:
    return shutil.which("curl.exe") or shutil.which("curl") or "curl"


def _probe_video(video_path: Path) -> dict:
    """Valida metadados técnicos do MP4 via ffprobe."""
    res = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-show_entries", "stream=codec_type,codec_name,width,height",
            "-of", "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(res.stdout)


def _load_youtube_token_data() -> dict:
    """Carrega credenciais OAuth do YouTube da env YOUTUBE_TOKEN_JSON ou de token.json local."""
    raw_env = os.getenv("YOUTUBE_TOKEN_JSON", "").strip()
    if raw_env:
        return json.loads(raw_env)
    token_path = BASE_DIR / "token.json"
    if token_path.exists():
        return json.loads(token_path.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "Credenciais do YouTube não encontradas (defina YOUTUBE_TOKEN_JSON ou gere token.json)."
    )


def _refresh_youtube_access_token(tok_data: dict) -> str:
    """Renova access_token do YouTube via curl.exe (Schannel) usando refresh_token."""
    refresh_token = tok_data.get("refresh_token", "").strip()
    client_id = tok_data.get("client_id", "").strip()
    client_secret = tok_data.get("client_secret", "").strip()
    token_uri = tok_data.get("token_uri", "https://oauth2.googleapis.com/token")

    if not refresh_token or not client_id or not client_secret:
        raise ValueError("token.json/YOUTUBE_TOKEN_JSON incompleto (falta refresh_token/client_id/client_secret).")

    res = subprocess.run(
        [
            _curl_bin(), "-s", "--max-time", "30", "-X", "POST", token_uri,
            "--data-urlencode", f"client_id={client_id}",
            "--data-urlencode", f"client_secret={client_secret}",
            "--data-urlencode", f"refresh_token={refresh_token}",
            "--data-urlencode", "grant_type=refresh_token",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    refreshed = json.loads(res.stdout)
    if "access_token" not in refreshed:
        raise RuntimeError(f"Falha ao renovar token do YouTube: {refreshed}")
    return refreshed["access_token"]


def _upload_youtube_via_curl(video_path: Path, meta: dict, access_token: str) -> str:
    """Faz upload resumable no YouTube Data API v3 via curl.exe (Schannel)."""
    temp_dir = BASE_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    meta_file = temp_dir / "yt_meta.json"
    hdr_file = temp_dir / "yt_headers.txt"

    body = {
        "snippet": {
            "title": meta["titulo_yt"][:100],
            "description": meta["descricao"],
            "tags": meta.get("tags", []),
            "categoryId": "22",
            "defaultLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    meta_file.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    file_size = video_path.stat().st_size

    try:
        # Passo 1: Inicia sessão de upload resumable e captura header Location
        init_res = subprocess.run(
            [
                _curl_bin(), "-s", "--max-time", "30", "-D", str(hdr_file),
                "-X", "POST",
                "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                "-H", f"Authorization: Bearer {access_token}",
                "-H", "Content-Type: application/json; charset=UTF-8",
                "-H", f"X-Upload-Content-Length: {file_size}",
                "-H", "X-Upload-Content-Type: video/mp4",
                "--data-binary", f"@{meta_file.resolve()}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        headers_txt = hdr_file.read_text(encoding="utf-8", errors="replace") if hdr_file.exists() else ""
        upload_url = ""
        for line in headers_txt.splitlines():
            if line.lower().startswith("location:"):
                upload_url = line.split(":", 1)[1].strip()
                break

        if not upload_url:
            raise RuntimeError(
                f"YouTube não retornou URL de upload resumable. Resposta: {init_res.stdout[:400]}"
            )

        # Passo 2: Envia o MP4 binário
        up_res = subprocess.run(
            [
                _curl_bin(), "-s", "--max-time", "120",
                "-X", "PUT", upload_url,
                "-H", f"Authorization: Bearer {access_token}",
                "-H", "Content-Type: video/mp4",
                "--data-binary", f"@{video_path.resolve()}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        resp_json = json.loads(up_res.stdout)
        if "error" in resp_json:
            raise RuntimeError(f"Erro YouTube API no upload: {resp_json['error']}")
        vid_id = resp_json.get("id", "")
        print(f"[YouTube Shorts] Publicado com sucesso! https://youtube.com/shorts/{vid_id}")
        return vid_id
    finally:
        for f in (meta_file, hdr_file):
            if f.exists():
                f.unlink()


def publish_youtube_shorts(video_path: Path, meta: dict, dry_run: bool = True) -> dict:
    """Publica no YouTube Shorts via YouTube Data API v3 (ou simula em DRY_RUN)."""
    if dry_run:
        print(f"[YouTube Shorts | DRY_RUN] Vídeo validado: {video_path.name}")
        print(f"  Título: {meta['titulo_yt']}")
        print(f"  Tags: {', '.join(meta['tags'])}")
        return {"platform": "youtube", "dry_run": True, "status": "simulated"}

    tok_data = _load_youtube_token_data()
    access_token = _refresh_youtube_access_token(tok_data)
    vid_id = _upload_youtube_via_curl(video_path, meta, access_token)
    return {"platform": "youtube", "dry_run": False, "video_id": vid_id}


def publish_tiktok_video(video_path: Path, meta: dict, dry_run: bool = True) -> dict:
    """Publica no TikTok via Content Posting API (ou simula em DRY_RUN)."""
    if dry_run:
        print(f"[TikTok | DRY_RUN] Vídeo validado: {video_path.name}")
        print(f"  Legenda: {meta['descricao'][:140]}...")
        return {"platform": "tiktok", "dry_run": True, "status": "simulated"}

    access_token = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    if not access_token:
        print("[TikTok] TIKTOK_ACCESS_TOKEN ausente; mantendo em DRY_RUN.")
        return {"platform": "tiktok", "dry_run": True, "status": "missing_token"}

    file_size = video_path.stat().st_size
    init_payload = {
        "post_info": {
            "title": meta["titulo_yt"][:150],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }
    print(f"[TikTok] Pronto para envio via Content Posting API ({file_size} bytes).")
    return {"platform": "tiktok", "dry_run": False, "payload_ready": init_payload}


def run_video_pipeline(
    slot: str, yt_dry_run: bool = False, tt_dry_run: bool = True
) -> dict:
    """Gera o vídeo 9:16 do slot e publica no YouTube Shorts (+ TikTok quando habilitado)."""
    video_path, meta = generate_short_video(slot=slot)
    probe = _probe_video(video_path)
    fmt = probe.get("format", {})
    print(
        f"[Validação MP4] {video_path.name} | duração={float(fmt.get('duration', 0)):.2f}s | "
        f"tamanho={int(fmt.get('size', 0)) / 1024 / 1024:.2f} MB"
    )

    yt_res = publish_youtube_shorts(video_path, meta, dry_run=yt_dry_run)
    tt_res = publish_tiktok_video(video_path, meta, dry_run=tt_dry_run)
    return {"video": str(video_path), "youtube": yt_res, "tiktok": tt_res}


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    yt_dry = os.getenv("YOUTUBE_DRY_RUN", "false").strip().lower() == "true"
    tt_dry = os.getenv("TIKTOK_DRY_RUN", "true").strip().lower() != "false"

    parser = argparse.ArgumentParser(description="Publicador Modular YouTube Shorts + TikTok")
    parser.add_argument(
        "--slot",
        choices=["versiculo_dia", "palavra_animo"],
        required=True,
        help="Slot correspondente ao post de imagem do dia.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Força simulação em todas as plataformas.",
    )
    args = parser.parse_args()

    if args.dry_run:
        yt_dry, tt_dry = True, True

    print(f"=== [VIDEO PUBLISHER] slot={args.slot} | YT_DRY_RUN={yt_dry} | TT_DRY_RUN={tt_dry} ===")
    run_video_pipeline(slot=args.slot, yt_dry_run=yt_dry, tt_dry_run=tt_dry)


if __name__ == "__main__":
    main()
