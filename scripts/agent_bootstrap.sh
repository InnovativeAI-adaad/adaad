#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# ADAAD Agent Bootstrap — One-command onboarding for Claude, Gemini, and Codex.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  ADAAD Agent Bootstrap — Adaptive Onboarding${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 1. Prerequisite Checks
echo -e "\n${BLUE}→ Checking prerequisites...${NC}"

if ! command -v node >/dev/null 2>&1; then
    echo -e "${RED}✗ node is missing. Install Node.js (v18+) to use Claude Code.${NC}"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}✗ python3 is missing. Install Python 3.11+ to run the ADAAD runtime.${NC}"
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo -e "${RED}✗ git is missing. Git is required for change classification and lineage.${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Prerequisites ok.${NC}"

# 2. Select Operating Profile
echo -e "\n${BLUE}→ Select operating profile:${NC}"
echo "  1) Fast     (Dev-only; skips expensive gates for documentation/minor changes)"
echo "  2) Standard (Balanced; full local validation)"
echo "  3) Release  (Governed; strict fail-closed release gates)"
read -p "Profile [1-3, default 1]: " PROFILE_CHOICE
PROFILE_CHOICE=${PROFILE_CHOICE:-1}

case $PROFILE_CHOICE in
    1) MODE="fast"; echo -e "${GREEN}✔ Profile: Fast Path enabled.${NC}" ;;
    2) MODE="standard"; echo -e "${GREEN}✔ Profile: Standard Path enabled.${NC}" ;;
    3) MODE="release"; echo -e "${GREEN}✔ Profile: Governed Release Path enabled.${NC}" ;;
    *) MODE="fast"; echo -e "${GREEN}✔ Profile: Defaulting to Fast Path.${NC}" ;;
esac

# 3. Configure API Keys
DOTENV=".env.local"
echo -e "\n${BLUE}→ Configuring API keys (skipping empty inputs)...${NC}"

[ ! -f "$DOTENV" ] && touch "$DOTENV"

read -p "Anthropic API Key (Claude): " ANTHROPIC_KEY
if [ -n "$ANTHROPIC_KEY" ]; then
    sed -i '/ADAAD_ANTHROPIC_API_KEY/d' "$DOTENV"
    echo "ADAAD_ANTHROPIC_API_KEY=$ANTHROPIC_KEY" >> "$DOTENV"
fi

read -p "Google Gemini API Key: " GEMINI_KEY
if [ -n "$GEMINI_KEY" ]; then
    sed -i '/GOOGLE_API_KEY/d' "$DOTENV"
    echo "GOOGLE_API_KEY=$GEMINI_KEY" >> "$DOTENV"
fi

read -p "OpenAI API Key (Codex): " OPENAI_KEY
if [ -n "$OPENAI_KEY" ]; then
    sed -i '/OPENAI_API_KEY/d' "$DOTENV"
    echo "OPENAI_KEY=$OPENAI_KEY" >> "$DOTENV"
fi

# Set mode in .env.local
sed -i '/ADAAD_FAST_MODE/d' "$DOTENV"
if [ "$MODE" == "fast" ]; then
    echo "ADAAD_FAST_MODE=true" >> "$DOTENV"
else
    echo "ADAAD_FAST_MODE=false" >> "$DOTENV"
fi

echo -e "${GREEN}✔ Configuration saved to $DOTENV.${NC}"

# 4. Smoke Test
echo -e "\n${BLUE}→ Running 60-second smoke task (summarize lane)...${NC}"
export ADAAD_ENV=dev
export $(cat "$DOTENV" | xargs)

python3 -m app.main --verbose --exit-after-boot

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ADAAD Onboarding Complete. Run an epoch:${NC}"
echo -e "${BLUE}  python3 -m app.main --verbose${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
