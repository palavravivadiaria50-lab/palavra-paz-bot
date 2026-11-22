"""Módulo A: Curadoria contextual cristã (Gemini) + Lookup 100% literal NTLH."""

import argparse
import json
import os
import subprocess
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    BRT_TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    BRT_TZ = timezone(timedelta(hours=-3))


BASE_DIR = Path(__file__).resolve().parent.parent
BIBLIA_NTLH_PATH = BASE_DIR / "data" / "biblia_ntlh.json"
HISTORICO_PATH = BASE_DIR / "data" / "historico_versiculos.json"
TEMP_DIR = BASE_DIR / "temp"

SYSTEM_PROMPT = (
    "Você é o editor devocional oficial do canal evangélico Palavra & Paz (@palavraepaz.oficial). "
    "DIRETRIZES PERMANENTES INEGOCIÁVEIS: "
    "1) Deus ao centro de tudo: Em qualquer versículo, devocional, frase motivacional ou legenda, "
    "Deus e Jesus Cristo devem ser apresentados como o centro e a resposta para todas as situações "
    "(nunca autoajuda secular sem Deus). "
    "2) Identidade exclusivamente cristã evangélica: Todo conteúdo deve seguir estritamente a doutrina "
    "e a linguagem cristã evangélica bíblica, evitando sincretismo ou termos de outras religiões."
)

FALLBACK_CURADO = [
    ("Salmos", 23, 1),
    ("Filipenses", 4, 6),
    ("Mateus", 11, 28),
    ("Isaías", 41, 10),
    ("Romanos", 8, 28),
    ("Provérbios", 3, 5),
    ("Josué", 1, 9),
    ("Salmos", 46, 10),
    ("Jeremias", 29, 11),
    ("Filipenses", 4, 13),
    ("1 Pedro", 5, 7),
    ("João", 14, 27),
    ("Salmos", 121, 2),
    ("Mateus", 6, 33),
    ("Romanos", 12, 12),
    ("2 Coríntios", 12, 9),
    ("Salmos", 91, 1),
    ("Isaías", 40, 31),
    ("João", 16, 33),
    ("Salmos", 37, 5),
    ("Tiago", 1, 5),
    ("1 João", 4, 18),
    ("Salmos", 119, 105),
    ("Lamentações", 3, 22),
    ("Efésios", 3, 20),
    ("Salmos", 27, 1),
    ("Romanos", 15, 13),
    ("Salmos", 34, 18),
    ("Hebreus", 11, 1),
    ("Mateus", 28, 20),
]


WEEKLY_CONTEXT_MAP = {
    1: {
        "dia_nome": "Segunda-feira",
        "tema_semanal": "Recomeço, Força e Ânimo",
        "contexto": "Início de semana; muitas pessoas acordam desanimadas ou ansiosas com trabalho e desafios.",
        "tom": (
            "Encorajador de recomeço, coragem e entrega da semana a Deus. "
            "PROIBIDO falar de 'fim de semana' ou 'descanso da semana que passou'."
        ),
        "exemplos": "Josué 1:9, Lamentações 3:22-23, Salmos 37:5, Isaías 41:10",
    },
    2: {
        "dia_nome": "Terça-feira",
        "tema_semanal": "Perseverança, Foco e Confiança",
        "contexto": "Meio da semana, rotina pesada e cansaço acumulado.",
        "tom": "Perseverança, sabedoria nas decisões, paciência e paz no meio da correria.",
        "exemplos": "Gálatas 6:9, Provérbios 3:5-6, Filipenses 4:6-7, Romanos 12:12",
    },
    3: {
        "dia_nome": "Quarta-feira",
        "tema_semanal": "Perseverança, Foco e Confiança",
        "contexto": "Meio da semana, rotina pesada e cansaço acumulado.",
        "tom": "Perseverança, sabedoria nas decisões, paciência e paz no meio da correria.",
        "exemplos": "Gálatas 6:9, Provérbios 3:5-6, Filipenses 4:6-7, Romanos 12:12",
    },
    4: {
        "dia_nome": "Quinta-feira",
        "tema_semanal": "Perseverança, Foco e Confiança",
        "contexto": "Meio da semana, rotina pesada e cansaço acumulado.",
        "tom": "Perseverança, sabedoria nas decisões, paciência e paz no meio da correria.",
        "exemplos": "Gálatas 6:9, Provérbios 3:5-6, Filipenses 4:6-7, Romanos 12:12",
    },
    5: {
        "dia_nome": "Sexta-feira",
        "tema_semanal": "Gratidão pela Semana Vencida e Alívio",
        "contexto": "Encerramento da semana útil, dever cumprido e transição para o descanso.",
        "tom": "Gratidão por Deus ter sustentado até aqui, livramentos da semana e entrega do cansaço.",
        "exemplos": "Salmos 126:3, Salmos 103:2, Mateus 11:28",
    },
    6: {
        "dia_nome": "Sábado",
        "tema_semanal": "Descanso, Família, Leveza e Renovação",
        "contexto": "Dia de desacelerar, curtir a família e renovar as energias.",
        "tom": "Leve e acolhedor, focado em paz no lar, descanso da alma e alegria.",
        "exemplos": "Salmos 23:2-3, Salmos 127:1-2, Eclesiastes 3:12-13, Salmos 4:8",
    },
    7: {
        "dia_nome": "Domingo",
        "tema_semanal": "Adoração, Comunhão, Gratidão e Preparo Espiritual",
        "contexto": "Dia do Senhor, culto/igreja, reflexão profunda e preparo espiritual para a nova semana.",
        "tom": "Adoração, presença de Deus, renovação espiritual e esperança.",
        "exemplos": "Salmos 122:1, Salmos 118:24, Hebreus 10:24-25, Salmos 95:1-2",
    },
}


def get_weekly_context(weekday: int | None = None) -> dict:
    """Retorna o contexto semanal cristão para o dia da semana em America/Sao_Paulo (1=Seg..7=Dom)."""
    if weekday is None:
        weekday = datetime.now(BRT_TZ).isoweekday()
    weekday = max(1, min(7, int(weekday)))
    info = WEEKLY_CONTEXT_MAP[weekday]
    prompt_bloco = (
        f"{info['dia_nome']} ({info['tema_semanal']}): "
        f"Contexto: {info['contexto']} "
        f"Tom: {info['tom']} "
        f"Referências inspiradoras (sem repetir histórico): {info['exemplos']}."
    )
    return {"weekday": weekday, **info, "prompt_bloco": prompt_bloco}


def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _load_biblia_index(biblia_path: Path = BIBLIA_NTLH_PATH) -> tuple[dict, dict]:
    """Carrega índice exato {(livro_norm, cap, ver): (nome_oficial, texto)}."""
    if not biblia_path.exists():
        raise FileNotFoundError(f"Base NTLH não encontrada em: {biblia_path}")
    biblia = json.loads(biblia_path.read_text(encoding="utf-8-sig"))
    index = {}
    aliases = {}
    for livro in biblia:
        nome = livro["name"]
        aliases[_norm(nome)] = nome
        for ci, caps in enumerate(livro["chapters"], start=1):
            for vi, txt_raw in enumerate(caps, start=1):
                texto = " ".join(str(txt_raw).split()).strip()
                index[(_norm(nome), ci, vi)] = (nome, texto)
    return index, aliases


def buscar_versiculo_ntlh(
    livro: str, capitulo: int, versiculo: int, index: dict | None = None
) -> dict | None:
    """Faz lookup exato de (livro, capitulo, versiculo) em data/biblia_ntlh.json."""
    if index is None:
        index, _ = _load_biblia_index()
    key = (_norm(livro), int(capitulo), int(versiculo))
    if key == (_norm("Salmo"), int(capitulo), int(versiculo)):
        key = (_norm("Salmos"), int(capitulo), int(versiculo))
    hit = index.get(key)
    if not hit:
        return None
    nome_oficial, texto = hit
    return {
        "referencia": f"{nome_oficial} {int(capitulo)}:{int(versiculo)} (NTLH)",
        "texto": texto,
        "livro": nome_oficial,
        "capitulo": int(capitulo),
        "versiculo": int(versiculo),
    }


def _call_gemini_curl(prompt: str, api_key: str) -> dict:
    """Chama Gemini REST API via curl.exe (Schannel) com System Prompt permanente."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    payload_file = TEMP_DIR / "temp_payload.json"
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
        },
    }
    payload_file.write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    last_err = None
    try:
        for _ in range(3):
            for model in ("gemini-2.5-flash", "gemini-3-flash-preview"):
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={api_key}"
                )
                try:
                    res = subprocess.run(
                        [
                            "curl.exe",
                            "-s",
                            "--max-time",
                            "90",
                            "-H",
                            "Content-Type: application/json",
                            "-d",
                            f"@{payload_file.resolve()}",
                            url,
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        check=True,
                    )
                except subprocess.CalledProcessError as exc:
                    last_err = f"curl exit {exc.returncode} em {model}"
                    continue

                raw = res.stdout.strip()
                if not raw:
                    last_err = f"Resposta vazia do modelo {model}"
                    continue
                resp_json = json.loads(raw)
                if "error" in resp_json:
                    last_err = resp_json["error"]
                    continue
                text_out = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text_out)
            time.sleep(3)
    finally:
        if payload_file.exists():
            payload_file.unlink()

    raise RuntimeError(f"Falha na Gemini REST API via curl.exe: {last_err}")


def generate_weekly_batch(output_path: Path, force: bool = False) -> dict:
    """Gera lote semanal (07:00, 08:00, 15:00, 20:30) com lookup literal NTLH."""
    if output_path.exists() and not force:
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        dias_ex = existing.get("dias", {})
        if (
            "dia_1" in dias_ex
            and "devocional_manha" in dias_ex["dia_1"]
            and "palavra_animo" in dias_ex["dia_1"]
        ):
            return existing

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY não encontrada no .env.")

    index, _ = _load_biblia_index()
    if HISTORICO_PATH.exists():
        historico: list[str] = json.loads(HISTORICO_PATH.read_text(encoding="utf-8"))
    else:
        historico = []
        HISTORICO_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORICO_PATH.write_text("[]", encoding="utf-8")

    usados = set(historico)
    proibidos_str = ", ".join(historico[-60:]) if historico else "nenhum"
    contexto_semanal_prompt = "\n".join(
        f"- dia_{i} -> {get_weekly_context(i)['prompt_bloco']}" for i in range(1, 8)
    )

    prompt = f"""Crie o conteúdo semanal completo para 7 dias ("dia_1" = Segunda-feira até "dia_7" = Domingo) na grade oficial de 4 horários diários (07:00, 08:00, 15:00, 20:30).

INTELIGÊNCIA DE CONTEXTO SEMANAL (OBRIGATÓRIO ADAPTAR CADA DIA AO SEU MOMENTO REAL DA SEMANA):
{contexto_semanal_prompt}

REGRAS ESTRITAS NA ESCOLHA DOS VERSÍCULOS:
- Escolha referências bíblicas **autoexplicativas, edificantes e de impacto imediato** (promessas de Deus, palavras de Jesus, consolo, sabedoria, fé e esperança).
- PROIBIDO escolher versículos narrativos isolados ou que comecem no meio de uma frase.
- PROIBIDO repetir qualquer referência desta lista já usada: [{proibidos_str}]
- Escolha versículos entre 55 e 210 caracteres.
- NÃO use emojis dentro dos textos dos cards/slides.

Temas obrigatórios para o bloco `palavra_animo` (15:00) ao longo dos 7 dias (sempre colocando Deus e Jesus Cristo como a resposta, nunca autoajuda secular):
- dia_1: coragem
- dia_2: propósito
- dia_3: perseverança
- dia_4: gratidão
- dia_5: confiança nos planos de Deus
- dia_6: recomeço
- dia_7: consolo

Para cada dia ("dia_1" a "dia_7"), retorne exatamente:
{{
  "devocional_manha": {{
    "livro": "Nome exato do livro",
    "capitulo": 23,
    "versiculo": 1,
    "titulo": "Título curto da meditação matinal (máx 45 chars)",
    "slide_2_reflexao": "Reflexão devocional estilo Manhã e Noite de C.H. Spurgeon alinhada ao versículo (máx 200 chars)",
    "slide_3_oracao": "Oração curta e aplicação prática para o dia (máx 180 chars)",
    "query_pixabay_foto": "termo simples em inglês (ex: dark wooden table minimalist coffee cup, shadow wall minimalist beige)",
    "legenda_ig": "Legenda acolhedora para o carrossel da manhã + 5 hashtags limpas"
  }},
  "versiculo_dia": {{
    "livro": "Nome exato do livro",
    "capitulo": 4,
    "versiculo": 6,
    "query_pixabay_foto": "termo simples em inglês (ex: moody coffee cup ceramic, cozy warm soft background)",
    "legenda_ig": "Legenda breve e acolhedora + 5 hashtags limpas"
  }},
  "palavra_animo": {{
    "tema": "tema do dia",
    "frase_motivacional": "Frase marcante, cristocêntrica e compartilhável colocando Deus como resposta (máx 210 chars, sem emojis)",
    "livro": "Nome exato do livro para o versículo âncora",
    "capitulo": 1,
    "versiculo": 9,
    "legenda": "Legenda evangélica acolhedora para Feed com chamada natural para compartilhar + 5 hashtags limpas"
  }},
  "devocional_noite": {{
    "livro": "Nome exato do livro",
    "capitulo": 11,
    "versiculo": 28,
    "titulo": "Título curto da meditação noturna (máx 45 chars)",
    "slide_2_reflexao": "Reflexão noturna de descanso e confiança em Deus estilo Spurgeon (máx 200 chars)",
    "slide_3_oracao": "Oração breve de entrega antes de dormir (máx 180 chars)",
    "query_pixabay_foto": "termo simples em inglês (ex: dark warm natural linen background, calm sea dark sunset)",
    "legenda_ig": "Legenda serena para o carrossel da noite + 5 hashtags limpas"
  }}
}}

Retorne um JSON com a chave raiz "dias" contendo "dia_1" a "dia_7".
"""

    data = _call_gemini_curl(prompt, api_key)
    raw_dias = data.get("dias", data)
    if isinstance(raw_dias, list):
        dias = {f"dia_{i}": item for i, item in enumerate(raw_dias, start=1)}
    elif isinstance(raw_dias, dict) and "dia_1" in raw_dias:
        dias = raw_dias
    else:
        raise ValueError(f"Formato inesperado do Gemini: chaves={list(data.keys())}")

    def _pick_valid_verse(bloco: dict) -> dict:
        try:
            hit = buscar_versiculo_ntlh(
                str(bloco.get("livro", "")),
                int(bloco.get("capitulo", 0)),
                int(bloco.get("versiculo", 0)),
                index=index,
            )
            if (
                hit
                and hit["referencia"] not in usados
                and not hit["texto"][0].islower()
            ):
                usados.add(hit["referencia"])
                return hit
        except Exception:
            pass

        for lv, cp, vr in FALLBACK_CURADO:
            hit = buscar_versiculo_ntlh(lv, cp, vr, index=index)
            if hit and hit["referencia"] not in usados:
                usados.add(hit["referencia"])
                return hit

        raise RuntimeError("Sem versículos disponíveis no fallback curado.")

    novas_refs: list[str] = []
    ctas_rotacao = [
        "\n\nEnvie esta palavra para alguém que precisa hoje.",
        "\n\n📖 Para aprofundar seu momento diário com Deus, deixamos devocionais e materiais de edificação separados no link da bio @palavraepaz.oficial",
    ]
    for idx in range(1, 8):
        key = f"dia_{idx}"
        d = dias[key]

        v_manha = _pick_valid_verse(d["devocional_manha"])
        d["devocional_manha"]["slide_1_texto"] = v_manha["texto"]
        d["devocional_manha"]["referencia_biblica"] = v_manha["referencia"]
        d["devocional_manha"]["estilo_visual"] = (
            "papel_minimalista" if idx % 2 == 1 else "foto_aesthetic"
        )
        novas_refs.append(v_manha["referencia"])

        v_dia = _pick_valid_verse(d["versiculo_dia"])
        d["versiculo_dia"]["texto_card"] = v_dia["texto"]
        d["versiculo_dia"]["referencia_biblica"] = v_dia["referencia"]
        d["versiculo_dia"]["estilo_visual"] = (
            "foto_aesthetic" if idx % 2 == 1 else "papel_minimalista"
        )
        novas_refs.append(v_dia["referencia"])

        v_animo = _pick_valid_verse(d["palavra_animo"])
        d["palavra_animo"]["versiculo_ancora"] = v_animo["texto"]
        d["palavra_animo"]["referencia_ancora"] = v_animo["referencia"]
        d["palavra_animo"]["estilo_papel"] = (
            "creme" if idx % 2 == 1 else "carvao"
        )
        cta_animo = ctas_rotacao[(idx - 1) % 2]
        if "@palavraepaz.oficial" not in d["palavra_animo"].get("legenda", ""):
            d["palavra_animo"]["legenda"] = d["palavra_animo"]["legenda"].rstrip() + cta_animo
        novas_refs.append(v_animo["referencia"])

        v_noite = _pick_valid_verse(d["devocional_noite"])
        d["devocional_noite"]["slide_1_texto"] = v_noite["texto"]
        d["devocional_noite"]["referencia_biblica"] = v_noite["referencia"]
        d["devocional_noite"]["estilo_visual"] = (
            "foto_aesthetic" if idx % 2 == 1 else "papel_minimalista"
        )
        cta_noite = ctas_rotacao[idx % 2]
        if "@palavraepaz.oficial" not in d["devocional_noite"].get("legenda_ig", ""):
            d["devocional_noite"]["legenda_ig"] = d["devocional_noite"]["legenda_ig"].rstrip() + cta_noite
        novas_refs.append(v_noite["referencia"])

    historico.extend(novas_refs)
    HISTORICO_PATH.write_text(
        json.dumps(historico, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    data["dias"] = dias
    data["generated_at"] = datetime.now().isoformat(timespec="seconds")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def verify_batch_literal_ntlh(batch_path: Path) -> list[tuple[str, str, bool]]:
    """Valida se todos os 28 versículos do lote são 100% literais da base NTLH."""
    biblia = json.loads(BIBLIA_NTLH_PATH.read_text(encoding="utf-8-sig"))
    lookup = {}
    for livro in biblia:
        for ci, caps in enumerate(livro["chapters"], start=1):
            for vi, txt in enumerate(caps, start=1):
                ref = f"{livro['name']} {ci}:{vi} (NTLH)"
                lookup[ref] = " ".join(str(txt).split()).strip()

    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    results = []
    for dia_k, d in batch["dias"].items():
        for bloco, campo_txt, campo_ref in (
            ("devocional_manha", "slide_1_texto", "referencia_biblica"),
            ("versiculo_dia", "texto_card", "referencia_biblica"),
            ("palavra_animo", "versiculo_ancora", "referencia_ancora"),
            ("devocional_noite", "slide_1_texto", "referencia_biblica"),
        ):
            ref = d[bloco][campo_ref]
            txt = d[bloco][campo_txt]
            ok = lookup.get(ref) == txt
            results.append((f"{dia_k}.{bloco}", ref, ok))
    return results


CTAS_ROTACAO = [
    "\n\nEnvie esta palavra para alguém que precisa hoje.",
    "\n\n📖 Para aprofundar seu momento diário com Deus, deixamos devocionais e materiais de edificação separados no link da bio @palavraepaz.oficial",
]


def ensure_subtle_cta(day_key: str, day_data: dict) -> dict:
    """Garante rotação discreta de CTA em palavra_animo (15:00) e devocional_noite (20:30)."""
    try:
        idx = int(day_key.split("_")[-1])
    except Exception:
        idx = 1

    pa = day_data.get("palavra_animo")
    if isinstance(pa, dict):
        leg = pa.get("legenda", "").rstrip()
        if "@palavraepaz.oficial" not in leg and "Envie esta palavra para alguém que precisa hoje." not in leg:
            pa["legenda"] = leg + CTAS_ROTACAO[(idx - 1) % 2]

    dn = day_data.get("devocional_noite")
    if isinstance(dn, dict):
        leg = dn.get("legenda_ig", "").rstrip()
        if "@palavraepaz.oficial" not in leg and "Envie esta palavra para alguém que precisa hoje." not in leg:
            dn["legenda_ig"] = leg + CTAS_ROTACAO[idx % 2]

    return day_data


def get_day_content(batch_path: Path, day_index: int | None = None) -> tuple[str, dict]:
    """Retorna (chave_dia, conteudo) do lote semanal no fuso America/Sao_Paulo."""
    batch = generate_weekly_batch(batch_path, force=False)
    if day_index is None:
        day_index = datetime.now(BRT_TZ).isoweekday()
    day_key = f"dia_{day_index}"
    dias = batch.get("dias", batch)
    if day_key not in dias:
        day_key = "dia_1"
    return day_key, ensure_subtle_cta(day_key, dias[day_key])


def _run_dry_run_demo() -> None:
    """Simula a adaptação de contexto semanal para hoje (BRT) e para uma Segunda-feira."""
    hoje_ctx = get_weekly_context()
    segunda_ctx = get_weekly_context(weekday=1)

    print("=== [DRY-RUN] Inteligência de Contexto Semanal (America/Sao_Paulo) ===")
    for label, ctx in (("HOJE (real BRT)", hoje_ctx), ("SEGUNDA-FEIRA (simulada)", segunda_ctx)):
        print(f"\n[{label}] {ctx['dia_nome']} — {ctx['tema_semanal']}")
        print(f"  Contexto: {ctx['contexto']}")
        print(f"  Tom:      {ctx['tom']}")
        print(f"  Exemplos: {ctx['exemplos']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerador de Conteúdo Semanal NTLH")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula contexto semanal para hoje (BRT) e Segunda-feira sem alterar arquivos.",
    )
    args = parser.parse_args()
    if args.dry_run:
        _run_dry_run_demo()
