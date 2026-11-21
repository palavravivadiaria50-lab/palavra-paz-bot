"""Publicador modular para YouTube Shorts (Data API v3) e TikTok (Content Posting API)."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.video_generator import BASE_DIR, generate_short_video


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


def publish_youtube_shorts(video_path: Path, meta: dict, dry_run: bool = True) -> dict:
    """Publica no YouTube Shorts via YouTube Data API v3 (ou simula em DRY_RUN)."""
    if dry_run:
        print(f"[YouTube Shorts | DRY_RUN] Vídeo validado: {video_path.name}")
        print(f"  Título: {meta['titulo_yt']}")
        print(f"  Tags: {', '.join(meta['tags'])}")
        return {"platform": "youtube", "dry_run": True, "status": "simulated"}

    from src.publishers.youtube_publisher import publish_youtube_short

    vid_id = publish_youtube_short(
        video_path=video_path,
        title=meta["titulo_yt"],
        description=meta["descricao"],
        tags=meta["tags"],
        client_secret_path=BASE_DIR / "client_secret.json",
        token_path=BASE_DIR / "token.json",
    )
    return {"platform": "youtube", "dry_run": False, "video_id": vid_id}


def publish_tiktok_video(video_path: Path, meta: dict, dry_run: bool = True) -> dict:
    """Publica no TikTok via Content Posting API (ou simula em DRY_RUN)."""
    if dry_run:
        print(f"[TikTok | DRY_RUN] Vídeo validado: {video_path.name}")
        print(f"  Legenda: {meta['descricao'][:140]}...")
        return {"platform": "tiktok", "dry_run": True, "status": "simulated"}

    access_token = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise ValueError("TIKTOK_ACCESS_TOKEN não configurado nos Secrets/.env.")

    # Estrutura oficial da TikTok Content Posting API v2 (FILE_UPLOAD)
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


def run_video_pipeline(slot: str, dry_run: bool = True) -> dict:
    """Gera o vídeo 9:16 do slot e executa publicação (ou DRY_RUN) no YouTube Shorts + TikTok."""
    video_path, meta = generate_short_video(slot=slot)
    probe = _probe_video(video_path)
    fmt = probe.get("format", {})
    print(
        f"[Validação MP4] {video_path.name} | duração={float(fmt.get('duration', 0)):.2f}s | "
        f"tamanho={int(fmt.get('size', 0)) / 1024 / 1024:.2f} MB"
    )

    yt_res = publish_youtube_shorts(video_path, meta, dry_run=dry_run)
    tt_res = publish_tiktok_video(video_path, meta, dry_run=dry_run)
    return {"video": str(video_path), "youtube": yt_res, "tiktok": tt_res}


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    env_dry = os.getenv("DRY_RUN", "true").strip().lower() != "false"

    parser = argparse.ArgumentParser(description="Publicador Modular YouTube Shorts + TikTok")
    parser.add_argument(
        "--slot",
        choices=["versiculo_dia", "palavra_animo"],
        required=True,
        help="Slot correspondente ao post de imagem do dia.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Desativa DRY_RUN e envia via APIs oficiais (requer tokens configurados).",
    )
    args = parser.parse_args()

    dry_run = False if args.live else env_dry
    print(f"=== [VIDEO PUBLISHER] slot={args.slot} | DRY_RUN={dry_run} ===")
    run_video_pipeline(slot=args.slot, dry_run=dry_run)


if __name__ == "__main__":
    main()
