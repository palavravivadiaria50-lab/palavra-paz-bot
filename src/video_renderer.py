"""Módulo B: Motor de vídeo curto 9:16 (~7-10s) apenas com versículo bíblico JFA + playback de oração."""

import json
import os
import random
import re
import subprocess
import textwrap
from pathlib import Path


def _strip_emojis(text: str) -> str:
    """Remove emojis para evitar quadrados vazios no drawtext do FFmpeg."""
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    cleaned = re.sub(r"[\u2600-\u27BF\uFE0F]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _escape_ffmpeg_path(path: Path) -> str:
    """Escapa caminho do Windows para uso dentro de filtros FFmpeg (ex: C\\:/...)."""
    posix = path.resolve().as_posix()
    return posix.replace(":", "\\:").replace("'", "\\'")


def _escape_drawtext_inline(text: str) -> str:
    """Escapa texto inline para drawtext (dois-pontos, aspas simples/duplas, %)."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("%", "\\%")
    )


def _curl_get_json(url: str, params: dict) -> dict:
    """Consulta JSON via curl.exe nativo (Schannel) evitando erros SSL no Windows."""
    cmd = ["curl.exe", "-s", "--max-time", "30", "-G", url]
    for k, v in params.items():
        cmd.extend(["--data-urlencode", f"{k}={v}"])
    res = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(res.stdout)


def _curl_download(url: str, dest: Path) -> None:
    """Baixa arquivo binário via curl.exe nativo (Schannel)."""
    subprocess.run(
        ["curl.exe", "-s", "-L", "--max-time", "60", "-o", str(dest), url],
        check=True,
    )


def _fetch_pixabay_video(
    query: str, temp_dir: Path, assets_videos_dir: Path
) -> Path:
    """Baixa 1 vídeo vertical da Pixabay API via curl.exe ou usa assets/videos/."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()

    if api_key:
        try:
            data = _curl_get_json(
                "https://pixabay.com/api/videos/",
                {
                    "key": api_key,
                    "q": query,
                    "orientation": "vertical",
                    "per_page": "10",
                    "safesearch": "true",
                },
            )
            hits = data.get("hits", [])
            if hits:
                chosen = random.choice(hits[:5])
                vid_id = chosen["id"]
                out_mp4 = temp_dir / f"pixabay_{vid_id}.mp4"
                if out_mp4.exists() and out_mp4.stat().st_size > 0:
                    return out_mp4

                videos = chosen.get("videos", {})
                stream = (
                    videos.get("large") or videos.get("medium") or videos.get("small")
                )
                if stream and stream.get("url"):
                    _curl_download(stream["url"], out_mp4)
                    if out_mp4.exists() and out_mp4.stat().st_size > 0:
                        return out_mp4
        except Exception as exc:
            print(f"[Aviso] Pixabay vídeo falhou para '{query}': {exc}")

    if assets_videos_dir.exists():
        locals_mp4 = [
            p
            for p in assets_videos_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv"}
        ]
        if locals_mp4:
            return random.choice(locals_mp4)

    fallback = temp_dir / "fallback_bg.mp4"
    if not fallback.exists():
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x111827:s=1080x1920:d=10:r=30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(fallback),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return fallback


def _pick_or_generate_music(music_dir: Path, temp_dir: Path, duration: float) -> Path:
    """Seleciona MP3 devocional de assets/music/ ou gera pad instrumental suave de fallback."""
    if music_dir.exists():
        tracks = [
            p
            for p in music_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a"}
        ]
        if tracks:
            return random.choice(tracks)

    pad_wav = temp_dir / "ambient_pad.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            (
                f"aevalsrc=0.12*sin(2*PI*261.63*t)+0.09*sin(2*PI*329.63*t)"
                f"+0.09*sin(2*PI*392.00*t)+0.06*sin(2*PI*493.88*t):s=44100:d={duration:.2f}"
            ),
            "-af",
            "lowpass=f=650,volume=0.35",
            str(pad_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return pad_wav


def render_short_video(
    video_data: dict,
    output_mp4: Path,
    temp_dir: Path,
    assets_videos_dir: Path,
    assets_music_dir: Path,
    handle: str = "@palavraepaz",
) -> Path:
    """Renderiza vídeo curto (~7-10s, estilo loop/GIF) apenas com o versículo JFA na tela."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    versiculo = _strip_emojis(video_data["versiculo_jfa"])
    wrapped_verse = "\n".join(textwrap.wrap(versiculo, width=26))

    # Duração curta entre 7s e 10s proporcional ao tamanho do versículo
    duration = min(10.0, max(7.0, 4.0 + len(versiculo) * 0.04))

    bg_video = _fetch_pixabay_video(
        video_data.get("query_pixabay_video", "sunrise clouds"),
        temp_dir,
        assets_videos_dir,
    )
    music_path = _pick_or_generate_music(assets_music_dir, temp_dir, duration)

    font_path = Path("C:/Windows/Fonts/georgiab.ttf")
    if not font_path.exists():
        font_path = Path("C:/Windows/Fonts/arialbd.ttf")
    font_esc = _escape_ffmpeg_path(font_path)

    verse_txt = temp_dir / "versiculo.txt"
    verse_txt.write_text(wrapped_verse, encoding="utf-8")
    verse_esc = _escape_ffmpeg_path(verse_txt)
    handle_esc = _escape_drawtext_inline(_strip_emojis(handle))

    fade_out_start = max(0.0, duration - 1.5)
    filter_script_path = temp_dir / "filter_complex.txt"
    filter_str = (
        "[0:v]"
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,fps=30,"
        "eq=brightness=-0.15:contrast=1.05,"
        f"drawtext=fontfile='{font_esc}':textfile='{verse_esc}':"
        "fontcolor=#FFFFFF:fontsize=54:line_spacing=16:"
        "borderw=3:bordercolor=black@0.75:"
        "x=(w-text_w)/2:y=(h-text_h)/2,"
        f"drawtext=fontfile='{font_esc}':text='{handle_esc}':"
        "fontcolor=#FFFFFF@0.75:fontsize=34:"
        "borderw=2:bordercolor=black@0.5:"
        "x=(w-text_w)/2:y=h-220"
        "[vout];"
        f"[1:a]volume=0.85,afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=1.5[aout]"
    )
    filter_script_path.write_text(filter_str, encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(bg_video.resolve()),
        "-stream_loop",
        "-1",
        "-i",
        str(music_path.resolve()),
        "-/filter_complex",
        str(filter_script_path.resolve()),
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-t",
        f"{duration:.2f}",
        "-c:v",
        "libx264",
        "-b:v",
        "3.5M",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_mp4.resolve()),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_mp4
