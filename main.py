"""Módulo E: Orquestrador Principal do Palavra & Paz (Apenas Imagens — Vídeo Desativado)."""

import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

from src.card_renderer import render_animo_card, render_card, render_carousel
from src.content_generator import (
    generate_weekly_batch,
    get_day_content,
    verify_batch_literal_ntlh,
)
from src.meta_publisher import (
    publish_carousel,
    publish_single_post,
    publish_story,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_BATCH = BASE_DIR / "data" / "weekly_batch.json"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"


def run_test(handle: str) -> None:
    print("=== [TEST] Gerando lote semanal NTLH via curl.exe ===")
    generate_weekly_batch(DATA_BATCH, force=True)

    print("=== [TEST] Validando fidelidade literal NTLH (28 versículos) ===")
    checks = verify_batch_literal_ntlh(DATA_BATCH)
    for label, ref, ok in checks:
        print(f"  {label:24s} | {ref:30s} | LITERAL_OK={ok}")
    all_ok = all(ok for _, _, ok in checks)
    print(f"Resumo LITERAL_OK: {sum(1 for _, _, ok in checks if ok)}/{len(checks)} (all={all_ok})")

    day_key, day_data = get_day_content(DATA_BATCH, day_index=1)
    dm = day_data["devocional_manha"]
    vd = day_data["versiculo_dia"]
    pa = day_data["palavra_animo"]
    dn = day_data["devocional_noite"]

    print(f"\n=== [TEST] Renderizando cards locais em output/ ({day_key}) ===")
    manha_paths = [
        OUTPUT_DIR / "test_dev_manha_1.jpg",
        OUTPUT_DIR / "test_dev_manha_2.jpg",
        OUTPUT_DIR / "test_dev_manha_3.jpg",
    ]
    render_carousel(dm, manha_paths, TEMP_DIR / "test_cards", handle=handle)

    vers_path = OUTPUT_DIR / "test_versiculo.jpg"
    render_card(
        texto=vd["texto_card"],
        estilo_visual=vd["estilo_visual"],
        output_jpg=vers_path,
        temp_dir=TEMP_DIR / "test_cards",
        referencia_biblica=vd["referencia_biblica"],
        query_foto=vd.get("query_pixabay_foto", "moody coffee cup ceramic"),
        handle=handle,
    )

    animo_path = OUTPUT_DIR / "test_animo.jpg"
    render_animo_card(
        frase_motivacional=pa["frase_motivacional"],
        versiculo_ancora=pa["versiculo_ancora"],
        referencia_ancora=pa["referencia_ancora"],
        output_jpg=animo_path,
        estilo_papel=pa.get("estilo_papel", "creme"),
        handle=handle,
    )

    noite_paths = [
        OUTPUT_DIR / "test_dev_noite_1.jpg",
        OUTPUT_DIR / "test_dev_noite_2.jpg",
        OUTPUT_DIR / "test_dev_noite_3.jpg",
    ]
    render_carousel(dn, noite_paths, TEMP_DIR / "test_cards", handle=handle)
    print("[OK] Todos os cards de teste renderizados em output/ (sem publicar).")


def run_slot(slot: str, handle: str) -> None:
    """Roteia cada bloco oficial respeitando a Matriz de Distribuição (apenas imagens)."""
    day_key, day_data = get_day_content(DATA_BATCH)
    print(f"=== [SLOT: {slot}] Processando {day_key} ===")

    if slot == "devocional_manha":
        dm = day_data["devocional_manha"]
        paths = [OUTPUT_DIR / f"{day_key}_dev_manha_{i}.jpg" for i in (1, 2, 3)]
        render_carousel(dm, paths, TEMP_DIR / day_key, handle=handle)
        publish_carousel(paths, dm["legenda_ig"])

    elif slot == "versiculo_dia":
        vd = day_data["versiculo_dia"]
        card_path = OUTPUT_DIR / f"{day_key}_versiculo.jpg"
        render_card(
            texto=vd["texto_card"],
            estilo_visual=vd["estilo_visual"],
            output_jpg=card_path,
            temp_dir=TEMP_DIR / day_key,
            referencia_biblica=vd["referencia_biblica"],
            query_foto=vd.get("query_pixabay_foto", "moody coffee cup ceramic"),
            handle=handle,
        )
        publish_single_post(card_path, vd["legenda_ig"])
        publish_story(card_path)

    elif slot == "palavra_animo":
        pa = day_data["palavra_animo"]
        card_path = OUTPUT_DIR / f"{day_key}_animo.jpg"
        render_animo_card(
            frase_motivacional=pa["frase_motivacional"],
            versiculo_ancora=pa["versiculo_ancora"],
            referencia_ancora=pa["referencia_ancora"],
            output_jpg=card_path,
            estilo_papel=pa.get("estilo_papel", "creme"),
            handle=handle,
        )
        publish_single_post(card_path, pa["legenda"])
        publish_story(card_path)

    elif slot == "devocional_noite":
        dn = day_data["devocional_noite"]
        paths = [OUTPUT_DIR / f"{day_key}_dev_noite_{i}.jpg" for i in (1, 2, 3)]
        render_carousel(dn, paths, TEMP_DIR / day_key, handle=handle)
        publish_carousel(paths, dn["legenda_ig"])

    else:
        raise ValueError(f"Slot desconhecido: {slot}")


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    handle = os.getenv("CHANNEL_HANDLE", "@palavraepaz.oficial")

    parser = argparse.ArgumentParser(
        description="Palavra & Paz - Pipeline Automatizado (Apenas Imagens)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--test",
        action="store_true",
        help="Gera lote NTLH e renderiza os cards de teste localmente.",
    )
    group.add_argument(
        "--slot",
        choices=[
            "devocional_manha",
            "versiculo_dia",
            "palavra_animo",
            "devocional_noite",
        ],
        help="Executa a renderização e publicação oficial do bloco.",
    )

    args = parser.parse_args()
    if args.test:
        run_test(handle)
    elif args.slot:
        run_slot(args.slot, handle)


if __name__ == "__main__":
    main()
