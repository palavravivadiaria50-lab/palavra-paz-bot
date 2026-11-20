"""Módulo C: Motor de Cards Minimalistas 4:5 (1080x1350) e Stories 9:16 (1080x1920)."""

import json
import math
import os
import random
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


CARD_W = 1080
CARD_H = 1350
STORY_W = 1080
STORY_H = 1920
_LOCAL_PHOTO_INDEX = 0


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_chars: int = 30,
) -> list[str]:
    """Quebra texto respeitando largura máxima em pixels e limite de ~30 chars por linha."""
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


def _pick_local_photo(photos_dir: Path) -> Path | None:
    """Seleciona imagens locais em assets/photos/ em rodízio."""
    global _LOCAL_PHOTO_INDEX
    if not photos_dir.exists():
        return None
    files = [
        p
        for p in sorted(photos_dir.iterdir())
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if not files:
        return None
    chosen = files[_LOCAL_PHOTO_INDEX % len(files)]
    _LOCAL_PHOTO_INDEX += 1
    return chosen


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
        ["curl.exe", "-s", "-L", "--max-time", "30", "-o", str(dest), url],
        check=True,
    )


def _fetch_pixabay_photo(query: str, temp_dir: Path) -> Path | None:
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key:
        return None
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = _curl_get_json(
            "https://pixabay.com/api/",
            {
                "key": api_key,
                "q": query,
                "image_type": "photo",
                "orientation": "vertical",
                "per_page": "10",
                "safesearch": "true",
            },
        )
        hits = data.get("hits", [])
        if not hits:
            return None
        chosen = random.choice(hits[:5])
        url = chosen.get("largeImageURL") or chosen.get("webformatURL")
        if not url:
            return None
        out_path = temp_dir / f"pixabay_photo_{chosen['id']}.jpg"
        if not out_path.exists() or out_path.stat().st_size == 0:
            _curl_download(url, out_path)
        return out_path
    except Exception as exc:
        print(f"[Aviso] Pixabay foto falhou para '{query}': {exc}")
        return None


def _create_paper_background(
    bg_rgb: tuple[int, int, int] = (247, 245, 240),
    width: int = CARD_W,
    height: int = CARD_H,
) -> Image.Image:
    """Cria fundo editorial com textura sutil de papel."""
    r0, g0, b0 = bg_rgb
    img = Image.new("RGB", (width, height), bg_rgb)
    pixels = img.load()
    rng = random.Random(42)
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            delta = rng.randint(-4, 4)
            r = max(0, min(255, r0 + delta))
            g = max(0, min(255, g0 + delta))
            b = max(0, min(255, b0 + delta))
            pixels[x, y] = (r, g, b)
            if x + 1 < width:
                pixels[x + 1, y] = (r, g, b)
            if y + 1 < height:
                pixels[x, y + 1] = (r, g, b)
    return img


def _build_vignette_layer(width: int = CARD_W, height: int = CARD_H) -> Image.Image:
    """Gera camada RGBA de vinheta suave nas bordas."""
    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = vignette.load()
    cx, cy = width / 2.0, height / 2.0
    max_dist = math.hypot(cx, cy)

    for y in range(0, height, 4):
        dy = y - cy
        for x in range(0, width, 4):
            dx = x - cx
            ratio = math.hypot(dx, dy) / max_dist
            alpha = int(max(0.0, (ratio - 0.45) / 0.55) ** 1.6 * 85)
            val = (10, 8, 6, min(255, alpha))
            for yy in range(y, min(y + 4, height)):
                for xx in range(x, min(x + 4, width)):
                    px[xx, yy] = val
    return vignette


def _resolve_photo_path(
    query: str, temp_dir: Path, photos_dir: Path | None = None
) -> Path | None:
    photo_path = _pick_local_photo(photos_dir) if photos_dir else None
    if photo_path is None:
        photo_path = _fetch_pixabay_photo(query, temp_dir)
    return photo_path


def _create_photo_background(
    query: str,
    temp_dir: Path,
    photos_dir: Path | None = None,
    width: int = CARD_W,
    height: int = CARD_H,
    photo_path: Path | None = None,
) -> Image.Image:
    """Usa foto local ou Pixabay com crop central, blur(5), overlay RGBA(20,15,10,120) e vinheta."""
    if photo_path is None:
        photo_path = _resolve_photo_path(query, temp_dir, photos_dir=photos_dir)

    if photo_path and photo_path.exists():
        base = Image.open(photo_path).convert("RGB")
        ratio = max(width / base.width, height / base.height)
        new_w = int(base.width * ratio)
        new_h = int(base.height * ratio)
        base = base.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        base = base.crop((left, top, left + width, top + height))
    else:
        base = Image.new("RGB", (width, height), (42, 36, 30))

    base = base.filter(ImageFilter.GaussianBlur(radius=5))
    overlay = Image.new("RGBA", (width, height), (20, 15, 10, 120))
    combined = Image.alpha_composite(base.convert("RGBA"), overlay)
    vignette = _build_vignette_layer(width=width, height=height)
    combined = Image.alpha_composite(combined, vignette)
    return combined.convert("RGB")


def _render_on_base(
    base_img: Image.Image,
    is_paper: bool,
    texto: str,
    output_jpg: Path,
    referencia_biblica: str = "",
    topo_label: str = "",
    slide_tag: str = "",
    handle: str = "@palavraepaz.oficial",
    is_story: bool = False,
) -> Path:
    """Renderiza texto, referência, topo e rodapé respeitando Safe Zone de Feed (4:5) ou Story (9:16)."""
    img = base_img.copy()
    w, h = img.size

    if is_paper:
        text_color = (28, 28, 28)       # #1C1C1C
        ref_color = (74, 70, 64)        # #4A4640
        meta_color = (110, 106, 99)     # #6E6A63
    else:
        text_color = (252, 250, 246)    # #FCFAF6 creme/branco suave
        ref_color = (244, 240, 232)
        meta_color = (232, 228, 220)

    font_main = _load_font(
        ["C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/times.ttf"], size=48
    )
    font_ref = _load_font(
        ["C:/Windows/Fonts/georgiai.ttf", "C:/Windows/Fonts/timesi.ttf"], size=34
    )
    font_small = _load_font(
        ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf"], size=28
    )

    draw = ImageDraw.Draw(img)
    margin_x = 140 if not is_story else 130  # >= 110px safe zone lateral
    top_y = 275 if is_story else 95          # >= 260px safe zone superior nos Stories
    footer_y = (h - 265) if is_story else 1240  # >= 240px safe zone inferior nos Stories

    max_text_w = w - (margin_x * 2)
    lines = _wrap_text(draw, texto.strip(), font_main, max_text_w, max_chars=30)
    line_height = int(48 * 1.45)
    block_h = len(lines) * line_height
    start_y = (h - block_h) // 2 - (30 if referencia_biblica else 0)

    top_left = topo_label or (datetime.now().strftime("%d.%m") if is_paper else "")

    if is_paper:
        if top_left:
            draw.text((margin_x, top_y), top_left, font=font_small, fill=meta_color)
        if slide_tag:
            sb = draw.textbbox((0, 0), slide_tag, font=font_small)
            draw.text((w - margin_x - (sb[2] - sb[0]), top_y), slide_tag, font=font_small, fill=meta_color)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_main)
            lw = bbox[2] - bbox[0]
            x = (w - lw) // 2
            y = start_y + i * line_height
            draw.text((x, y), line, font=font_main, fill=text_color)

        if referencia_biblica:
            ref_bbox = draw.textbbox((0, 0), referencia_biblica, font=font_ref)
            rw = ref_bbox[2] - ref_bbox[0]
            draw.text(
                (w - margin_x - rw, start_y + block_h + 36),
                referencia_biblica,
                font=font_ref,
                fill=ref_color,
            )
    else:
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_layer)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_main)
            lw = bbox[2] - bbox[0]
            x = (w - lw) // 2
            y = start_y + i * line_height
            s_draw.text((x + 2, y + 2), line, font=font_main, fill=(0, 0, 0, 150))

        if referencia_biblica:
            ref_bbox = draw.textbbox((0, 0), referencia_biblica, font=font_ref)
            rw = ref_bbox[2] - ref_bbox[0]
            s_draw.text(
                (w - margin_x - rw + 2, start_y + block_h + 38),
                referencia_biblica,
                font=font_ref,
                fill=(0, 0, 0, 150),
            )

        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=2))
        img = Image.alpha_composite(img.convert("RGBA"), shadow_layer).convert("RGB")
        draw = ImageDraw.Draw(img)

        if top_left:
            draw.text((margin_x, top_y), top_left, font=font_small, fill=meta_color)
        if slide_tag:
            sb = draw.textbbox((0, 0), slide_tag, font=font_small)
            draw.text((w - margin_x - (sb[2] - sb[0]), top_y), slide_tag, font=font_small, fill=meta_color)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_main)
            lw = bbox[2] - bbox[0]
            x = (w - lw) // 2
            y = start_y + i * line_height
            draw.text((x, y), line, font=font_main, fill=text_color)

        if referencia_biblica:
            ref_bbox = draw.textbbox((0, 0), referencia_biblica, font=font_ref)
            rw = ref_bbox[2] - ref_bbox[0]
            draw.text(
                (w - margin_x - rw, start_y + block_h + 36),
                referencia_biblica,
                font=font_ref,
                fill=ref_color,
            )

    h_bbox = draw.textbbox((0, 0), handle, font=font_small)
    hw = h_bbox[2] - h_bbox[0]
    draw.text(((w - hw) // 2, footer_y), handle, font=font_small, fill=meta_color)

    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_jpg, format="JPEG", quality=95)
    return output_jpg


def render_card(
    texto: str,
    estilo_visual: str,
    output_jpg: Path,
    temp_dir: Path,
    referencia_biblica: str = "",
    query_foto: str = "dark wooden table minimalist coffee cup",
    handle: str = "@palavraepaz.oficial",
    paper_color: tuple[int, int, int] = (247, 245, 240),
    photos_dir: Path | None = None,
    story_jpg: Path | None = None,
) -> Path:
    """Renderiza card único 4:5 (1080x1350) e opcionalmente a versão nativa Stories 9:16 (1080x1920)."""
    if photos_dir is None:
        photos_dir = output_jpg.resolve().parent.parent / "assets" / "photos"

    is_paper = estilo_visual == "papel_minimalista"
    chosen_photo = (
        None
        if is_paper
        else _resolve_photo_path(query_foto, temp_dir, photos_dir=photos_dir)
    )

    base_img = (
        _create_paper_background(bg_rgb=paper_color, width=CARD_W, height=CARD_H)
        if is_paper
        else _create_photo_background(
            query_foto,
            temp_dir,
            photos_dir=photos_dir,
            width=CARD_W,
            height=CARD_H,
            photo_path=chosen_photo,
        )
    )
    _render_on_base(
        base_img=base_img,
        is_paper=is_paper,
        texto=texto,
        output_jpg=output_jpg,
        referencia_biblica=referencia_biblica,
        handle=handle,
        is_story=False,
    )

    if story_jpg is not None:
        story_base = (
            _create_paper_background(bg_rgb=paper_color, width=STORY_W, height=STORY_H)
            if is_paper
            else _create_photo_background(
                query_foto,
                temp_dir,
                photos_dir=photos_dir,
                width=STORY_W,
                height=STORY_H,
                photo_path=chosen_photo,
            )
        )
        _render_on_base(
            base_img=story_base,
            is_paper=is_paper,
            texto=texto,
            output_jpg=story_jpg,
            referencia_biblica=referencia_biblica,
            handle=handle,
            is_story=True,
        )

    return output_jpg


def render_carousel(
    devocional_data: dict,
    output_paths: list[Path],
    temp_dir: Path,
    handle: str = "@palavraepaz.oficial",
    paper_color: tuple[int, int, int] = (247, 245, 240),
    photos_dir: Path | None = None,
) -> list[Path]:
    """Renderiza carrossel de 3 slides 4:5 (1080x1350) mantendo a mesma base visual."""
    if len(output_paths) != 3:
        raise ValueError("render_carousel requer exatamente 3 caminhos de saída.")

    if photos_dir is None:
        photos_dir = output_paths[0].resolve().parent.parent / "assets" / "photos"

    is_paper = devocional_data["estilo_visual"] == "papel_minimalista"
    base_img = (
        _create_paper_background(bg_rgb=paper_color, width=CARD_W, height=CARD_H)
        if is_paper
        else _create_photo_background(
            devocional_data.get("query_pixabay_foto", "cozy warm soft background"),
            temp_dir,
            photos_dir=photos_dir,
            width=CARD_W,
            height=CARD_H,
        )
    )

    titulo = devocional_data.get("titulo", "").strip()
    slides_spec = [
        (devocional_data["slide_1_texto"], devocional_data.get("referencia_biblica", ""), titulo, "1/3"),
        (devocional_data["slide_2_reflexao"], "", "Meditação", "2/3"),
        (devocional_data["slide_3_oracao"], "", "Oração", "3/3"),
    ]

    for idx, (texto, ref, topo, tag) in enumerate(slides_spec):
        _render_on_base(
            base_img=base_img,
            is_paper=is_paper,
            texto=texto,
            output_jpg=output_paths[idx],
            referencia_biblica=ref,
            topo_label=topo,
            slide_tag=tag,
            handle=handle,
            is_story=False,
        )
    return output_paths


def _draw_animo_canvas(
    frase_motivacional: str,
    versiculo_ancora: str,
    referencia_ancora: str,
    output_jpg: Path,
    estilo_papel: str,
    handle: str,
    width: int,
    height: int,
    is_story: bool,
) -> Path:
    is_dark = estilo_papel == "carvao"
    if is_dark:
        bg_rgb = (28, 27, 26)          # #1C1B1A
        main_color = (247, 245, 240)   # #F7F5F0
        verse_color = (210, 205, 198)
        line_color = (95, 90, 84)
        meta_color = (165, 160, 152)
    else:
        bg_rgb = (247, 245, 240)       # #F7F5F0
        main_color = (28, 28, 28)      # #1C1C1C
        verse_color = (74, 70, 64)
        line_color = (195, 189, 178)
        meta_color = (110, 106, 99)

    img = _create_paper_background(bg_rgb=bg_rgb, width=width, height=height)
    draw = ImageDraw.Draw(img)

    font_main = _load_font(
        ["C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/times.ttf"], size=46
    )
    font_verse = _load_font(
        ["C:/Windows/Fonts/georgiai.ttf", "C:/Windows/Fonts/timesi.ttf"], size=32
    )
    font_ref = _load_font(
        ["C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/times.ttf"], size=28
    )
    font_small = _load_font(
        ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf"], size=28
    )

    margin_x = 135 if not is_story else 130  # >= 110px safe zone lateral
    top_y = 275 if is_story else 95          # >= 260px safe zone superior
    footer_y = (height - 265) if is_story else 1240  # >= 240px safe zone inferior
    max_w = width - (margin_x * 2)

    date_str = datetime.now().strftime("%d.%m")
    draw.text((margin_x, top_y), date_str, font=font_small, fill=meta_color)

    main_lines = _wrap_text(draw, frase_motivacional.strip(), font_main, max_w, max_chars=30)
    main_lh = int(46 * 1.42)
    main_h = len(main_lines) * main_lh

    verse_lines = _wrap_text(draw, f'"{versiculo_ancora.strip()}"', font_verse, max_w, max_chars=42)
    verse_lh = int(32 * 1.38)
    verse_h = len(verse_lines) * verse_lh

    total_h = main_h + 44 + 44 + verse_h + 46
    min_start = 360 if is_story else 190
    start_y = max(min_start, (height - total_h) // 2)

    for i, line in enumerate(main_lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        lw = bbox[2] - bbox[0]
        draw.text(((width - lw) // 2, start_y + i * main_lh), line, font=font_main, fill=main_color)

    div_y = start_y + main_h + 44
    draw.line([(width // 2 - 90, div_y), (width // 2 + 90, div_y)], fill=line_color, width=2)

    v_start_y = div_y + 42
    for i, line in enumerate(verse_lines):
        bbox = draw.textbbox((0, 0), line, font=font_verse)
        lw = bbox[2] - bbox[0]
        draw.text(((width - lw) // 2, v_start_y + i * verse_lh), line, font=font_verse, fill=verse_color)

    ref_bbox = draw.textbbox((0, 0), referencia_ancora, font=font_ref)
    rw = ref_bbox[2] - ref_bbox[0]
    draw.text(((width - rw) // 2, v_start_y + verse_h + 22), referencia_ancora, font=font_ref, fill=meta_color)

    h_bbox = draw.textbbox((0, 0), handle, font=font_small)
    hw = h_bbox[2] - h_bbox[0]
    draw.text(((width - hw) // 2, footer_y), handle, font=font_small, fill=meta_color)

    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_jpg, format="JPEG", quality=95)
    return output_jpg


def render_animo_card(
    frase_motivacional: str,
    versiculo_ancora: str,
    referencia_ancora: str,
    output_jpg: Path,
    estilo_papel: str = "creme",
    handle: str = "@palavraepaz.oficial",
    story_jpg: Path | None = None,
) -> Path:
    """Renderiza card editorial 4:5 (1080x1350) e opcionalmente Stories 9:16 (1080x1920)."""
    _draw_animo_canvas(
        frase_motivacional=frase_motivacional,
        versiculo_ancora=versiculo_ancora,
        referencia_ancora=referencia_ancora,
        output_jpg=output_jpg,
        estilo_papel=estilo_papel,
        handle=handle,
        width=CARD_W,
        height=CARD_H,
        is_story=False,
    )

    if story_jpg is not None:
        _draw_animo_canvas(
            frase_motivacional=frase_motivacional,
            versiculo_ancora=versiculo_ancora,
            referencia_ancora=referencia_ancora,
            output_jpg=story_jpg,
            estilo_papel=estilo_papel,
            handle=handle,
            width=STORY_W,
            height=STORY_H,
            is_story=True,
        )

    return output_jpg
