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
- *Nota:* Motor de vídeo (`Reels / YouTube Shorts / TikTok`) permanece **desativado/pausado** nesta etapa.

---

## Estado Atual (Validado e Travado)
- **Base Bíblica NTLH (`data/biblia_ntlh.json`) + Anti-Repetição (`data/historico_versiculos.json`):** Lookup 100% literal garantido pelo Python após curadoria contextual do Gemini.
- **Comunicação Externa (`curl.exe` / Schannel):** Todas as chamadas à Gemini REST API, Pixabay API e Meta Graph API v21.0 usam `curl.exe` nativo do Windows, evitando erros de SSL (`_ssl.c:1006`).
- **Motor de Imagens (`src/card_renderer.py`):** Cards `1080x1350` validados (`papel_minimalista`, `foto_aesthetic` e card editorial `palavra_animo`).
- **Publicação Meta (`src/meta_publisher.py`):** Suporte completo a `publish_single_post`, `publish_carousel` (3 slides IG + multi-foto FB) e `publish_story` (IG Stories + FB `photo_stories`) via CDN nativa da Meta.
- **Agendamento GitHub Actions (`.github/workflows/daily_posts.yml`):** Configurado para os 4 horários BRT com commit/push automático de `data/historico_versiculos.json` e `data/weekly_batch.json`.

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
