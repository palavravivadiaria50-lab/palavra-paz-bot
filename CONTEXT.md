# CONTEXT.md — Dossiê Vivo do Projeto (`palavra-paz-bot` / `@palavraepaz.oficial`)

> **Última atualização:** 23/11/2026 — Este arquivo é o dossiê vivo oficial do projeto. Deve ser atualizado ao final de toda execução/conversa relevante e revisado antes de qualquer alteração.

## 1. Diretrizes Permanentes do Projeto (`@palavraepaz.oficial`)
1. **Deus ao centro de tudo:** Em qualquer versículo, devocional, frase motivacional ou vídeo, Deus e Jesus Cristo devem ser apresentados como o centro e a resposta para todas as situações (nunca autoajuda secular sem Deus).
2. **Identidade exclusivamente cristã evangélica:** Todo conteúdo deve seguir estritamente a doutrina e a linguagem cristã evangélica bíblica, evitando sincretismo ou termos de outras religiões.
3. **Execução controlada e memória travada:** Revisar este `CONTEXT.md` antes de qualquer alteração, preservar travado o uso de `curl.exe`/Schannel no Windows e o lookup literal em `data/biblia_ntlh.json`, e sempre atualizar este dossiê ao final das entregas.

---

## 2. Grade Oficial em Produção (Horário de Brasília — BRT)

### Imagens — Instagram & Facebook (`.github/workflows/daily_posts.yml`)
- **07:00 BRT (`0 10 * * *` UTC)** → `devocional_manha` — Carrossel 3 slides (`1080×1350`) → **Apenas Feed** (IG + FB).
- **08:00 BRT (`0 11 * * *` UTC)** → `versiculo_dia` — Card (`1080×1350` Feed) + Story nativo (`1080×1920`) → **Feed + Stories** (IG + FB).
- **15:00 BRT (`0 18 * * *` UTC)** → `palavra_animo` — Card (`1080×1350` Feed) + Story nativo (`1080×1920`) → **Feed + Stories** (IG + FB).
- **20:30 BRT (`30 23 * * *` UTC)** → `devocional_noite` — Carrossel 3 slides (`1080×1350`) → **Apenas Feed** (IG + FB).
- **Safe Zone Stories (`1080×1920`):** Topo `≥ 260px` (`275px`), rodapé `≥ 240px` (`265px`), laterais `≥ 110px` (`130px`).

### Vídeos Curtos — YouTube Shorts & TikTok (`.github/workflows/daily_videos.yml` — Isolado do IG/FB)
- **08:10 BRT (`10 11 * * *` UTC)** → `versiculo_dia` (10s, `1080×1920`, `30fps`).
- **15:10 BRT (`10 18 * * *` UTC)** → `palavra_animo` (10s, `1080×1920`, `30fps`).
- **YouTube Shorts:** **ATIVO** (`YOUTUBE_DRY_RUN='false'`) via `curl.exe` + Secret `YOUTUBE_TOKEN_JSON` (com descrição espelhada + link da vitrine + tentativa protegida de 1º comentário).
- **TikTok:** Em `TIKTOK_DRY_RUN='true'` (aguardando aprovação de app/token no TikTok for Developers).

### Monitoramento e Faxina — Watchdog (`.github/workflows/watchdog.yml`)
- **23:30 BRT (`30 2 * * *` UTC)** + gatilho automático `workflow_run` (30s após qualquer falha em `daily_posts.yml`).
- Valida workflows das últimas 24h (máx. 1 re-run automático em erros transitórios como `9007`/`2207027`/`is_transient`), tokens (Meta, Pixabay, Gemini), vitrine `palavraepaz.netlify.app`, abre/fecha Issues com rótulo `alerta-automacao` e executa retenção de mídia (limpa `temp/` e mantém no máx. 5 arquivos `≤ 2 dias` em `output/`).

---

## 3. Motores e Recursos Prontos
- **Conteúdo (`src/content_generator.py`):** Base literal NTLH (`data/biblia_ntlh.json`), anti-repetição (`data/historico_versiculos.json`), inteligência de contexto semanal (`get_weekly_context()` em `America/Sao_Paulo`), e CTA discreto garantido (`ensure_subtle_cta`) em `palavra_animo` e `devocional_noite`.
- **Cards (`src/card_renderer.py`):** `papel_minimalista`, `foto_aesthetic` (`GaussianBlur(5)`, overlay quente `RGBA(20,15,10,120)`, vinheta, `#FCFAF6`) e `palavra_animo` editorial, com auto-cleanup de fotos temporárias da Pixabay.
- **Publicação Meta (`src/meta_publisher.py`):** 100% via `curl.exe` (Schannel), upload oculto CDN nativa, retry progressivo (`10s/15s/20s` para erros `9007`/`2207027`) e anti-duplicidade via `data/status_publicacoes.json`.
- **Vídeos (`src/video_generator.py` + `src/video_publisher.py`):** Reaproveita textos de `data/weekly_batch.json` (0 tokens), fontes portáveis `assets/fonts/Lora-*.ttf`, 6 trilhas instrumentais de oração (`assets/audio/trilha_01.mp3` a `trilha_06.mp3`, `volume=0.45`, fade-in `1.5s`, fade-out `2.5s`), anti-repetição (`data/historico_videos.json`) e auto-cleanup imediato.

---

## 4. Vitrine Link da Bio (`links/` — `https://palavraepaz.netlify.app`)
- **Deploy Netlify:** Publish directory `links`.
- **Layout:** Grade responsiva (3 colunas desktop, 2 colunas tablet/mobile), logo `links/assets/logo.jpg`, **botão do YouTube (`https://www.youtube.com/@palavraepaz.oficial`) no topo** (estilo editorial branco/creme) e **6 materiais cristãos** com capas em `links/assets/produto_1..6`.
- **Créditos Netlify:** Protegido por `netlify.toml` (`ignore` quando `links/` não muda) + `[skip netlify]` nos commits automáticos. Reserva aproximada de ~60 créditos até renovação em **19/12/2026** (evitar deploys desnecessários em `links/` até lá).

---

## 5. Pendências Opcionais (Futuro)
- **Comentário automático no YouTube Shorts:** Re-autorizar `token.json` incluindo escopo `https://www.googleapis.com/auth/youtube.force-ssl` (hoje possui `youtube.upload`; o upload e a descrição com link já funcionam 100%).
- **TikTok API:** Configurar `TIKTOK_ACCESS_TOKEN` e alterar `TIKTOK_DRY_RUN='false'` quando o app for aprovado.
- **Botão YouTube vermelho na vitrine:** Avaliar após renovação dos créditos do Netlify em 19/12/2026.
