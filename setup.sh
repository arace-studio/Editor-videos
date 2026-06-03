#!/usr/bin/env bash
set -e

echo "=== Editor de Vídeos — Setup ==="

# Check ffmpeg
if ! command -v ffmpeg &>/dev/null; then
  echo "ERROR: ffmpeg não encontrado. Instale com:"
  echo "  macOS:  brew install ffmpeg"
  echo "  Ubuntu: sudo apt install ffmpeg"
  exit 1
fi
echo "✓ ffmpeg $(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3)"

# Check Node.js >= 22
if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js não encontrado. Instale em https://nodejs.org (versão 22+)"
  exit 1
fi
NODE_VER=$(node -e "process.stdout.write(process.version.slice(1))")
NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 22 ]; then
  echo "ERROR: Node.js $NODE_VER encontrado, mas versão 22+ é necessária"
  exit 1
fi
echo "✓ Node.js $NODE_VER"

# Check Python >= 3.10
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 não encontrado"
  exit 1
fi
PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VER" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VER" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
  echo "ERROR: Python $PYTHON_VER encontrado, mas versão 3.10+ é necessária"
  exit 1
fi
echo "✓ Python $PYTHON_VER"

# Install Python dependencies
echo ""
echo "Instalando dependências Python..."
if command -v uv &>/dev/null; then
  uv pip install -r requirements.txt
else
  python3 -m pip install -r requirements.txt
fi
echo "✓ Dependências Python instaladas"

# Install hyperframes globally
echo ""
echo "Instalando hyperframes..."
npm install -g hyperframes 2>/dev/null || npx --yes hyperframes --version &>/dev/null
echo "✓ hyperframes disponível"

# Create .env if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠  Arquivo .env criado. Preencha suas API keys:"
  echo "   ELEVENLABS_API_KEY=..."
  echo "   ANTHROPIC_API_KEY=..."
fi

echo ""
echo "=== Setup concluído! ==="
echo "Execute: python pipeline.py <seu_video.mp4>"
