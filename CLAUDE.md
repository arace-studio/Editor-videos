# Editor de Vídeos com IA

Pipeline que remove silêncios/repetições (video-use) e adiciona animações contextuais (hyperframes).

## Fluxo de trabalho

Quando o usuário enviar um vídeo:

1. Confirme recebimento e pergunte preferências se necessário (estilo, idioma, velocidade do corte)
2. Execute `python pipeline.py <caminho_do_video>` 
3. Relate o progresso em cada etapa
4. Entregue o vídeo final em `edit/final.mp4`

## Etapas do pipeline

### Etapa 1 — Transcrição
`helpers/transcribe.py` — ElevenLabs Scribe → JSON word-level com timestamps
- Cache em `edit/transcripts/`
- Re-transcreve apenas se o fonte mudou

### Etapa 2 — Corte de Silêncios e Repetições
`helpers/silence_cutter.py` — Analisa transcript → gera `edit/edl.json`
- Silêncios ≥ 400ms são cortados (silêncios < 150ms são mantidos)
- Frases repetidas consecutivas são detectadas e removidas
- Padding de 50ms em cada corte para evitar cortes abruptos

### Etapa 3 — Renderização do Vídeo Editado
`helpers/render.py` — Consome `edit/edl.json` → `edit/edited.mp4`
- Extração por segmento → concat lossless → normalização de áudio
- Fades de 30ms em cada corte (evita pops)
- Normalização LUFS -14 integrado

### Etapa 4 — Geração de Animações
`helpers/animation_generator.py` — Analisa transcript + chama Claude API → HTMLs em `edit/compositions/`
- Identifica: termos-chave, estatísticas, transições de tópico, nomes
- Gera composições hyperframes com GSAP

### Etapa 5 — Compositing Final
`helpers/compositor.py` — Renderiza HTMLs com hyperframes → compõe sobre vídeo editado → `edit/final.mp4`

## Setup inicial

```bash
bash setup.sh
cp .env.example .env
# Preencha ELEVENLABS_API_KEY e ANTHROPIC_API_KEY em .env
```

## Variáveis de ambiente necessárias

- `ELEVENLABS_API_KEY` — para transcrição Scribe
- `ANTHROPIC_API_KEY` — para análise de conteúdo e geração de animações

## Uso

```bash
# Processar um vídeo
python pipeline.py meu_video.mp4

# Apenas cortar silêncios (sem animações)
python pipeline.py meu_video.mp4 --no-animations

# Preview rápido (qualidade reduzida, mais rápido)
python pipeline.py meu_video.mp4 --preview

# Ajustar limiar de silêncio (padrão: 400ms)
python pipeline.py meu_video.mp4 --silence-threshold 300
```

## Saídas

```
edit/
├── transcripts/<video>.json     # Transcript word-level (cache)
├── takes_packed.md              # Transcript em markdown para revisão
├── edl.json                     # Lista de segmentos a manter
├── edited.mp4                   # Vídeo após cortes
├── compositions/                # HTMLs de animação gerados
│   ├── keyword_0001.html
│   └── stat_0002.html
└── final.mp4                    # Vídeo final com animações
```

## Tipos de animação gerados

- **keyword_highlight** — palavra-chave aparece na base da tela
- **stat_callout** — estatísticas/números animados com destaque
- **chapter_card** — transição com título do novo tópico
- **lower_third** — nome/cargo do apresentador

## Notas técnicas

- ffmpeg deve estar instalado (`brew install ffmpeg` ou `apt install ffmpeg`)
- Node.js ≥22 necessário para hyperframes
- Python ≥3.10 necessário
