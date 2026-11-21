# CONTEXT.md — Estado Atual do Projeto (`palavra-paz-bot`)

## Diretrizes Permanentes do Projeto (`@palavraepaz.oficial`)
1. **Deus ao centro de tudo:** Em qualquer versículo, devocional, frase motivacional ou vídeo, Deus e Jesus Cristo devem ser apresentados como o centro e a resposta para todas as situações (nunca autoajuda secular sem Deus).
2. **Identidade exclusivamente cristã evangélica:** Todo conteúdo deve seguir estritamente a doutrina e a linguagem cristã evangélica bíblica, evitando sincretismo ou termos de outras religiões.
3. **Execução controlada e memória travada:** Revisar este `CONTEXT.md` antes de qualquer alteração, preservar travado o uso de `curl.exe`/Schannel no Windows e o lookup literal em `data/biblia_ntlh.json`, e nunca alterar a etapa de vídeo sem aprovação explícita.

---

## Matriz Oficial de Distribuição de Imagens (Horário de Brasília — BRT)
- `07:00` (`devocional_manha`) → Carrossel 3 slides (`1080x1350`) → **Apenas Feed** (Instagram e Facebook).
- `08:00` (`versiculo_dia`) → Card Único (`1080x1350` Feed) + Versão Nativa (`1080x1920` Stories) → **Feed + Stories** (Instagram e Facebook).
- `15:00` (`palavra_animo`) → Card Único (`1080x1350` Feed) + Versão Nativa (`1080x1920` Stories) → **Feed + Stories** (Instagram e Facebook).
- `22:00` (`devocional_noite`) → Carrossel 3 slides (`1080x1350`) → **Apenas Feed** (Instagram e Facebook).
- **Safe Zone Stories (`1080x1920` — 9:16):** Margem superior `>= 260px`, margem inferior `>= 240px`, margens laterais `>= 110px` (evita zoom/corte automático do Instagram).

---

## Pipeline Modular de Vídeos Curtos (YouTube Shorts & TikTok — Isolado do IG/FB)
- **Isolamento estrito:** Fluxo de imagens (`daily_posts.yml` + `src/meta_publisher.py`) permanece 100% intacto e exclusivo para Instagram/Facebook.
- **Módulos:** `src/video_generator.py` (reaproveita textos de `data/weekly_batch.json` sem custo de tokens, baixa vídeos verticais HD da Pixabay sem repetir `data/historico_videos.json`, renderiza overlay Pillow + fade-in FFmpeg em `1080x1920`, `30fps`, `10s`, com trilha opcional em `assets/audio/` ou áudio silencioso válido) e `src/video_publisher.py` (YouTube Data API v3 + TikTok Content Posting API, operando inicialmente em `DRY_RUN=true`).
- **Agendamento (`.github/workflows/daily_videos.yml` — 10 min após os cards):**
  - `08:10 BRT` (`10 11 * * *` UTC) → `versiculo_dia`
  - `15:10 BRT` (`10 18 * * *` UTC) → `palavra_animo`

---

## Estado Atual (Validado e Travado)
- **Base Bíblica NTLH (`data/biblia_ntlh.json`) + Anti-Repetição (`data/historico_versiculos.json`):** Lookup 100% literal garantido pelo Python após curadoria contextual do Gemini.
- **Comunicação Externa (`curl.exe` / Schannel):** Todas as chamadas à Gemini REST API, Pixabay API e Meta Graph API v21.0 usam `curl.exe` nativo do Windows, evitando erros de SSL (`_ssl.c:1006`).
- **Motor de Imagens (`src/card_renderer.py`):** Cards `1080x1350` validados (`papel_minimalista`, `foto_aesthetic` e card editorial `palavra_animo`).
- **Publicação Meta (`src/meta_publisher.py`):** Suporte completo a `publish_single_post`, `publish_carousel` (3 slides IG + multi-foto FB) e `publish_story` (IG Stories + FB `photo_stories`) via CDN nativa da Meta, com **retry progressivo (4 tentativas: 10s, 15s, 20s)** para erros transitórios do Instagram (`code: 9007`, `error_subcode: 2207027`, `is_transient: true`) e registro anti-duplicidade em `data/status_publicacoes.json`.
- **Agendamento GitHub Actions (`.github/workflows/daily_posts.yml`):** Configurado para os 4 horários BRT com commit/push automático (`if: always()`) de `data/historico_versiculos.json`, `data/weekly_batch.json` e `data/status_publicacoes.json`.
- **Watchdog / Health Check (`.github/workflows/watchdog.yml` + `src/watchdog.py`):** Roda automaticamente **logo após qualquer falha de postagem (`workflow_run: completed`)** e também diariamente às `23:30 BRT` (`02:30 UTC`), verificando workflows das últimas 24h (com trava estrita de `run_attempt == 1` para no máximo 1 re-run automático em erros transitórios como `9007`/`2207027`/`is_transient`, sem risco de loop infinito e sem duplicar Facebook), validade dos tokens (Meta, Pixabay, Gemini), saúde da vitrine `palavraepaz.netlify.app` e abrindo/fechando Issues com rótulo `alerta-automacao`.

---

## Vitrine Link da Bio (`links/` — Deploy Netlify)
- **Publish directory no Netlify:** `links`
- **Arquivos:** `links/index.html`, `links/links.json`, `links/assets/logo.jpg` (capas opcionais em `links/assets/produto_1.jpg` a `produto_6.jpg` com fallback `P&P`).
- **6 Materiais Selecionados:**
  1. *Devocional 30 Dias com Deus para Ser uma Mulher Intencional* (Kiwify)
  2. *A Cura da Alma Através da Palavra* (Hotmart)
  3. *Devocionais Curtos para Começar o Dia com Fé* (Hotmart)
  4. *365 Dias com Jesus* (Hotmart)
  5. *Liderança Cristã Descomplicada para Adolescentes e Jovens* (Hotmart)
  6. *O Ministro de Louvor Completo* (Hotmart)
- **CTA sutil:** Rotação discreta ao final de `palavra_animo` (15:00) e `devocional_noite` (22:00) entre engajamento e menção ao link da bio `@palavraepaz.oficial`.
