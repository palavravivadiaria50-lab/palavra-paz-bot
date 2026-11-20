"""Preparação de pacote pronto para upload/agendamento no TikTok / Buffer."""

import shutil
from pathlib import Path


def prepare_tiktok_package(
    video_path: Path,
    legenda_tiktok: str,
    day_key: str,
    output_base_dir: Path,
) -> tuple[Path, Path]:
    """Copia vídeo e salva legenda UTF-8 em output/tiktok_pronto/."""
    dest_dir = output_base_dir / "tiktok_pronto"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_mp4 = dest_dir / f"{day_key}.mp4"
    dest_txt = dest_dir / f"{day_key}_legenda.txt"

    shutil.copy2(video_path, dest_mp4)
    dest_txt.write_text(legenda_tiktok.strip() + "\n", encoding="utf-8")

    print(f"[TikTok/Buffer] Pacote pronto em: {dest_dir}")
    return dest_mp4, dest_txt
