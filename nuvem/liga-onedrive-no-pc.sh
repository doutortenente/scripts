#!/usr/bin/env bash
# Liga o rclone do OneDrive no PC (host). Hermes já fez 95%: binário baixado, OAuth completo, token salvo.
# Este script só copia o config pro lugar que o host espera e testa.
# Feito em 2026-09-23. Rodar uma vez no terminal DO PC.

set -euo pipefail

# 1. binário onde os scripts esperam: arquivo único em ~/.local/bin (doc do rclone: binário pré-compilado;
#    atualizar com `rclone selfupdate`). Desde 25-out-2026 não fica mais dentro deste repo.
mkdir -p ~/.local/bin
[ -x ~/.local/bin/rclone ] || { echo 'falta ~/.local/bin/rclone: baixe de https://downloads.rclone.org/rclone-current-linux-amd64.zip' >&2; exit 1; }

# 2. config do remote (token já autorizado — NÃO pede login de novo)
mkdir -p ~/.config/rclone
cp ~/.hermes/home/.config/rclone/rclone.conf ~/.config/rclone/rclone.conf
chmod 600 ~/.config/rclone/rclone.conf

# 3. prova de vida
~/.local/bin/rclone listremotes
~/.local/bin/rclone about onedrive:
echo "PRONTO: rclone + OneDrive no ar. Ex: rclone ls onedrive:"
