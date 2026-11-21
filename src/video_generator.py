"""Gerador modular e rápido de vídeos curtos 9:16 (1080x1920, 10s) para YouTube Shorts e TikTok."""

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_BATCH = BASE_DIR / "data" / "weekly_batch.json"
HIST_VIDEOS = BASE_DIR / "data" / "historico_videos.json"
ASSETS_AUDIO = BASE_DIR / "assets" / "audio"
ASSETS_FONTS = BASE_DIR / "assets" / "fonts"
ASSETS_VIDEOS = BASE_DIR / "assets" / "videos"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp" / "shorts"

VIDEO_W = 1080
VIDEO_H = 1920
VIDEO_FPS = 30
VIDEO_DURATION = 10.0

PIXABAY_QUERIES = [
    "sunset clouds",
    "sunlight forest",
    "calm ocean waves",
    "golden field",
    "starry night sky",
]


def _curl_bin() -> str:
    return shutil.which("curl.exe") or shutil.which("curl") or "curl"


def _curl_get_json(url: str, params: dict) -> dict:
    cmd = [_curl_bin(), "-s", "--max-time", "20", "-G", url]
    for k, v in params.items():
        cmd.extend(["--data-urlencode", f"{k}={v}"])
    res = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", check=True, timeout=25
    )
    return json.loads(res.stdout)


def _curl_download(url: str, dest: Path) -> None:
    subprocess.run(
        [_curl_bin(), "-s", "-L", "--max-time", "20", "-o", str(dest), url],
        check=True,
        timeout=25,
    )


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_chars: int = 30,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0] <= max_width) and (len(test) <= max_chars or not current):
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def load_daily_text(slot: str, batch_path: Path = DATA_BATCH) -> dict:
    """Reaproveita o texto já gerado para o dia em data/weekly_batch.json (0 tokens extras)."""
    if not batch_path.exists():
        raise FileNotFoundError(f"Lote diário não encontrado em: {batch_path}")

    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    dias = batch.get("dias", {})
    if not dias:
        raise ValueError("Arquivo data/weekly_batch.json não possui chave 'dias'.")

    now_brt = datetime.now(timezone(timedelta(hours=-3)))
    day_key = f"dia_{now_brt.isoweekday()}"
    if day_key not in dias:
        day_key = sorted(dias.keys())[-1]

    day_data = dias[day_key]
    if slot == "palavra_animo":
        pa = day_data["palavra_animo"]
        return {
            "day_key": day_key,
            "slot": slot,
            "texto_principal": pa["frase_motivacional"].strip(),
            "referencia": pa.get("referencia_ancora", "").strip(),
            "titulo_yt": f"Palavra de Fé: {pa.get('tema', 'Ânimo').capitalize()} #Shorts",
            "descricao": f"{pa['frase_motivacional']}\n\n{pa.get('versiculo_ancora', '')} — {pa.get('referencia_ancora', '')}\n\n{pa.get('legenda', '')}",
            "tags": ["palavraepaz", "devocional", "fe", "deus", "jesus", "shorts", "motivacaocrista"],
        }

    vd = day_data["versiculo_dia"]
    ref = vd.get("referencia_biblica", "").strip()
    return {
        "day_key": day_key,
        "slot": "versiculo_dia",
        "texto_principal": vd["texto_card"].strip(),
        "referencia": ref,
        "titulo_yt": f"Versículo do Dia — {ref} #Shorts"[:70],
        "descricao": f"{vd['texto_card']} — {ref}\n\n{vd.get('legenda_ig', '')}",
        "tags": ["versiculododia", "biblia", "ntlh", "deus", "jesus", "palavraepaz", "shorts"],
    }


def fetch_pixabay_vertical_video(temp_dir: Path = TEMP_DIR) -> Path:
    """Busca vídeo vertical leve (medium/small, 720p-1080p) na Pixabay com timeout=20s."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()

    if HIST_VIDEOS.exists():
        try:
            used_ids: list[str] = json.loads(HIST_VIDEOS.read_text(encoding="utf-8"))
        except Exception:
            used_ids = []
    else:
        used_ids = []

    if api_key:
        queries = PIXABAY_QUERIES[:]
        random.shuffle(queries)
        for q in queries:
            try:
                data = _curl_get_json(
                    "https://pixabay.com/api/videos/",
                    {
                        "key": api_key,
                        "q": q,
                        "orientation": "vertical",
                        "per_page": "12",
                        "safesearch": "true",
                    },
                )
                hits = data.get("hits", [])
                random.shuffle(hits)
                fresh = [h for h in hits if str(h.get("id")) not in used_ids]
                pool = fresh or hits
                for chosen in pool:
                    vid_id = str(chosen["id"])
                    videos = chosen.get("videos", {})
                    # Prefere medium ou small (arquivos leves de ~3-10 MB, nunca 4K)
                    stream = videos.get("medium") or videos.get("small")
                    if not stream or not stream.get("url"):
                        continue
                    out_mp4 = temp_dir / f"pixabay_short_{vid_id}.mp4"
                    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
                        print(f"[Download] Baixando Pixabay '{q}' (id={vid_id})...")
                        _curl_download(stream["url"], out_mp4)
                    if out_mp4.exists() and out_mp4.stat().st_size > 0:
                        size_mb = out_mp4.stat().st_size / 1024 / 1024
                        print(f"[Download] Concluído ({size_mb:.2f} MB): {out_mp4.name}")
                        if vid_id not in used_ids:
                            used_ids.append(vid_id)
                            HIST_VIDEOS.parent.mkdir(parents=True, exist_ok=True)
                            HIST_VIDEOS.write_text(
                                json.dumps(used_ids[-60:], ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                        return out_mp4
            except Exception as exc:
                print(f"[Aviso] Pixabay vídeo falhou para '{q}': {exc}")

    if ASSETS_VIDEOS.exists():
        locals_mp4 = [
            p for p in ASSETS_VIDEOS.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv"}
        ]
        if locals_mp4:
            return random.choice(locals_mp4)

    fallback = temp_dir / "fallback_shorts_bg.mp4"
    if not fallback.exists():
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c=0x111827:s={VIDEO_W}x{VIDEO_H}:d={VIDEO_DURATION:.1f}:r={VIDEO_FPS}",
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(fallback),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    return fallback


def _render_combined_overlay_png(
    texto: str,
    referencia: str,
    output_png: Path,
    handle: str = "@palavraepaz.oficial",
) -> Path:
    """Gera 1 único PNG RGBA 1080x1920 (escurecimento + vinheta + texto estilo card foto_aesthetic)."""
    # 1. Escurecimento suave (~40%) + vinheta leve nas bordas
    base = Image.new("RGBA", (VIDEO_W, VIDEO_H), (15, 12, 10, 102))
    px = base.load()
    cx, cy = VIDEO_W / 2.0, VIDEO_H / 2.0
    max_dist = math.hypot(cx, cy)
    for y in range(0, VIDEO_H, 10):
        dy = y - cy
        for x in range(0, VIDEO_W, 10):
            dx = x - cx
            ratio = math.hypot(dx, dy) / max_dist
            extra = int(max(0.0, (ratio - 0.42) / 0.58) ** 1.5 * 68)
            val = (12, 10, 8, min(195, 102 + extra))
            for yy in range(y, min(y + 10, VIDEO_H)):
                for xx in range(x, min(x + 10, VIDEO_W)):
                    px[xx, yy] = val

    # 2. Fontes portáveis (assets/fonts/Lora-*.ttf com fallback Windows)
    font_main = _load_font(
        [
            str(ASSETS_FONTS / "Lora-Regular.ttf"),
            "C:/Windows/Fonts/georgia.ttf",
            "C:/Windows/Fonts/times.ttf",
        ],
        size=48,
    )
    font_ref = _load_font(
        [
            str(ASSETS_FONTS / "Lora-Italic.ttf"),
            "C:/Windows/Fonts/georgiai.ttf",
            "C:/Windows/Fonts/timesi.ttf",
        ],
        size=34,
    )
    font_handle = _load_font(
        [
            str(ASSETS_FONTS / "Lora-Regular.ttf"),
            "C:/Windows/Fonts/arial.ttf",
        ],
        size=28,
    )

    shadow = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    draw_tmp = ImageDraw.Draw(base)

    margin_x = 130
    max_text_w = VIDEO_W - (margin_x * 2)
    lines = _wrap_text(draw_tmp, texto, font_main, max_text_w, max_chars=30)
    lh = int(48 * 1.45)
    block_h = len(lines) * lh
    start_y = (VIDEO_H - block_h) // 2 - (30 if referencia else 0)

    for i, line in enumerate(lines):
        bbox = draw_tmp.textbbox((0, 0), line, font=font_main)
        lw = bbox[2] - bbox[0]
        x = (VIDEO_W - lw) // 2
        y = start_y + i * lh
        s_draw.text((x + 2, y + 2), line, font=font_main, fill=(0, 0, 0, 155))

    if referencia:
        rb = draw_tmp.textbbox((0, 0), referencia, font=font_ref)
        rw = rb[2] - rb[0]
        rx = VIDEO_W - margin_x - rw
        ry = start_y + block_h + 36
        s_draw.text((rx + 2, ry + 2), referencia, font=font_ref, fill=(0, 0, 0, 155))

    hb = draw_tmp.textbbox((0, 0), handle, font=font_handle)
    hw = hb[2] - hb[0]
    hx = (VIDEO_W - hw) // 2
    hy = VIDEO_H - 265
    s_draw.text((hx + 1, hy + 2), handle, font=font_handle, fill=(0, 0, 0, 130))

    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=2))
    combined = Image.alpha_composite(base, shadow)
    draw = ImageDraw.Draw(combined)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        lw = bbox[2] - bbox[0]
        x = (VIDEO_W - lw) // 2
        y = start_y + i * lh
        draw.text((x, y), line, font=font_main, fill=(252, 250, 246, 255))

    if referencia:
        rb = draw.textbbox((0, 0), referencia, font=font_ref)
        rw = rb[2] - rb[0]
        rx = VIDEO_W - margin_x - rw
        ry = start_y + block_h + 36
        draw.text((rx, ry), referencia, font=font_ref, fill=(244, 240, 232, 255))

    draw.text((hx, hy), handle, font=font_handle, fill=(232, 228, 220, 235))

    output_png.parent.mkdir(parents=True, exist_ok=True)
    combined.save(output_png, format="PNG")
    return output_png


def _pick_audio_track(audio_dir: Path = ASSETS_AUDIO) -> Path | None:
    if not audio_dir.exists():
        return None
    tracks = [
        p for p in audio_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a"}
    ]
    return random.choice(tracks) if tracks else None


def generate_short_video(
    slot: str = "versiculo_dia",
    output_mp4: Path | None = None,
    handle: str | None = None,
) -> tuple[Path, dict]:
    """Gera vídeo cinematográfico 1080x1920 (10s) em poucos segundos."""
    t0 = time.time()
    load_dotenv(BASE_DIR / ".env")
    channel_handle = handle or os.getenv("CHANNEL_HANDLE", "@palavraepaz.oficial")

    meta = load_daily_text(slot=slot)
    if output_mp4 is None:
        output_mp4 = OUTPUT_DIR / f"{meta['day_key']}_{slot}_shorts.mp4"

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    bg_mp4 = fetch_pixabay_vertical_video(TEMP_DIR)
    overlay_png = _render_combined_overlay_png(
        texto=meta["texto_principal"],
        referencia=meta["referencia"],
        output_png=TEMP_DIR / f"overlay_{meta['day_key']}_{slot}.png",
        handle=channel_handle,
    )
    audio_track = _pick_audio_track(ASSETS_AUDIO)

    fade_out_start = max(0.0, VIDEO_DURATION - 1.5)
    print("[Render] Iniciando FFmpeg (-preset veryfast -crf 23)...")

    if audio_track:
        filter_complex = (
            f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},setsar=1,fps={VIDEO_FPS}[bg];"
            f"[bg][1:v]overlay=0:0,"
            f"fade=t=in:st=0:d=0.8,fade=t=out:st={fade_out_start:.2f}:d=1.2,format=yuv420p[vout];"
            f"[2:a]volume=0.22,afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=1.5[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-t", f"{VIDEO_DURATION:.1f}", "-i", str(bg_mp4.resolve()),
            "-i", str(overlay_png.resolve()),
            "-stream_loop", "-1", "-t", f"{VIDEO_DURATION:.1f}", "-i", str(audio_track.resolve()),
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-t", f"{VIDEO_DURATION:.1f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_mp4.resolve()),
        ]
    else:
        filter_complex = (
            f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},setsar=1,fps={VIDEO_FPS}[bg];"
            f"[bg][1:v]overlay=0:0,"
            f"fade=t=in:st=0:d=0.8,fade=t=out:st={fade_out_start:.2f}:d=1.2,format=yuv420p[vout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-t", f"{VIDEO_DURATION:.1f}", "-i", str(bg_mp4.resolve()),
            "-i", str(overlay_png.resolve()),
            "-f", "lavfi", "-t", f"{VIDEO_DURATION:.1f}", "-i", "anullsrc=r=44100:cl=stereo",
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "2:a:0",
            "-t", f"{VIDEO_DURATION:.1f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_mp4.resolve()),
        ]

    subprocess.run(
        cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60
    )
    elapsed = time.time() - t0
    print(f"[Render] Concluído em {elapsed:.1f}s -> {output_mp4}")
    return output_mp4, meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerador de Vídeos Curtos 9:16 (YouTube Shorts / TikTok)")
    parser.add_argument(
        "--slot",
        choices=["versiculo_dia", "palavra_animo"],
        default="versiculo_dia",
        help="Slot do dia para reaproveitar o texto.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Gera vídeo de demonstração em output/teste_shorts.mp4.",
    )
    args = parser.parse_args()

    out_path = (OUTPUT_DIR / "teste_shorts.mp4") if args.test else None
    generate_short_video(slot=args.slot, output_mp4=out_path)


if __name__ == "__main__":
    main()
