# Gerador Automatizado de Vídeos Bíblicos (100% Gratuito)

Pipeline local em **Python + FFmpeg** inspirado no fluxo de criação de Reels/TikToks/Shorts bíblicos (9:16), substituindo o trabalho manual (ChatGPT + ElevenLabs + Canva + CapCut) por automação gratuita e legal.

## O que é usado (tudo grátis)
- **Narração + Timestamps:** `edge-tts` (vozes neurais em português do Brasil, sem chave de API, com marcação exata por palavra).
- **Legendas Dinâmicas:** Geradas automaticamente no formato `.ass` (1080x1920), com fonte grande, contorno forte e destaque amarelo na palavra falada.
- **Edição e Animação:** `FFmpeg` (já instalado no sistema), montando cenas em loop, aplicando movimento suave (*Ken Burns*) em imagens estáticas e queimando as legendas.
- **Roteiros:**
  - **Modo padrão:** Lê de [`data/roteiros_exemplo.json`](data/roteiros_exemplo.json) (já vem com 5 roteiros prontos).
  - **Modo Gemini API (grátis):** Usa a camada gratuita do [Google AI Studio](https://aistudio.google.com/apikey) (`GEMINI_API_KEY`).
  - **Aproveitando seu Google One Pro:** Você também pode pedir ao Gemini na web (ou gerar imagens no Gemini/Whisk/ImageFX) e salvar os arquivos JSON em `data/` ou as imagens 9:16 em `assets/backgrounds/`.
- **Fundos 9:16:**
  1. **Pexels API (grátis e legal):** Se `PEXELS_API_KEY` estiver no `.env`, baixa vídeos verticais livres de direitos autorais.
  2. **Pasta local:** Imagens (`.jpg`, `.png`) ou vídeos (`.mp4`) colocados em `assets/backgrounds/`.
  3. **Fallback automático:** Se não houver nenhum dos dois, o FFmpeg gera fundos animados suaves automaticamente.

## Instalação rápida
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Como usar

### 1. Gerar 1 vídeo agora (sem precisar de nenhuma chave de API)
```powershell
python gerar_video.py
```
O vídeo pronto (`1080x1920`) e o arquivo `post.txt` (com legenda + hashtags para copiar) serão salvos em `output/joao_3_16/`.

### 2. Gerar vários vídeos em lote
```powershell
python gerar_video.py --lote 5
```

### 3. Gerar roteiros inéditos com Gemini (camada gratuita do Google AI Studio)
1. Copie `.env.example` para `.env` e preencha `GEMINI_API_KEY` (e opcionalmente `PEXELS_API_KEY`).
2. Rode:
```powershell
python gerar_video.py --usar-gemini --lote 3 --tema "salmos de paz e confiança"
```

### 4. Opções úteis
- Trocar voz: `--voz pt-BR-FranciscaNeural` (feminina) ou `--voz pt-BR-AntonioNeural` (masculina).
- Ajustar velocidade: `--velocidade +15%` (padrão dinâmico) ou `--velocidade +0%`.
- Música ambiente: coloque arquivos `.mp3` sem direitos autorais em `assets/music/` e rode com `--com-musica` (ou deixe sem música para usar os áudios em alta direto no Instagram/TikTok, como recomendado no vídeo).
