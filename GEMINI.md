# GEMINI.md — Regras de Arquitetura e Governança (`palavra-paz-bot`)

## 1. Segurança e Isolamento
- **NUNCA** commitar `.env`, `client_secret.json` ou `token.json` no Git.
- Todas as credenciais devem ser carregadas exclusivamente via variáveis de ambiente (`python-dotenv`).
- Manter isolamento estrito de contas: este projeto publica apenas nos canais do **Palavra & Paz** (`@palavraepaz.oficial`).

## 2. Padrões de Codificação e Texto (UTF-8)
- Todos os arquivos `.json`, `.txt` e scripts Python devem usar explicitamente `encoding="utf-8"`.
- Preservar acentuação em português (`á`, `ã`, `ç`, `é`, etc.) sem corrupção de caracteres.
- Tradução bíblica obrigatória: **Almeida (JFA — João Ferreira de Almeida)**.

## 3. Padrões de Renderização FFmpeg (Windows)
- **Proibido usar emojis** em filtros `drawtext` do FFmpeg (evita renderização de quadrados vazios).
- Ao usar `drawtext` no Windows:
  - Escapar dois-pontos (`:`), aspas simples (`'`), contrabarras (`\`) e porcentagens (`%`), ou preferir `textfile=` em UTF-8 para evitar problemas de escaping no shell.
  - Caminhos de fonte no `drawtext` devem escapar o `:` do drive (ex: `C\:/Windows/Fonts/georgiab.ttf`).
- Especificação padrão de vídeo 9:16:
  - Resolução: `1080x1920` (`scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1`)
  - FPS: `30`, Codec de vídeo: `libx264`, Bitrate: `3.5M`, Pixel format: `yuv420p`
  - Áudio: `aac`, `128k`

## 4. Padrões de Cards Minimalistas (4:5)
- Resolução fixa: `1080x1350` (JPEG qualidade 95).
- Alternância diária entre `papel_minimalista` (`#F7F5F0`) e `foto_aesthetic` (foto Pixabay com overlay escuro `RGBA(0,0,0,95)`).
- Assinatura obrigatória discreta `@palavraepaz.oficial` no rodapé.

## 5. Dossiê Vivo (`CONTEXT.md`)
- Ao final de toda execução ou conversa relevante, atualizar o arquivo `CONTEXT.md` como dossiê vivo consolidando tudo o que está pronto, ativo e pendente.
- Commits que não alterem a pasta `links/` devem incluir `[skip netlify]` na mensagem para economizar créditos no Netlify.
