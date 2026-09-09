#!/usr/bin/env bash
# Otimização do Tijolão (03-jul-2026):
# 1) earlyoom  - vigia anti-congelamento: mata o processo mais gordo antes da RAM estourar
# 2) btop      - monitor de recursos pra VOCE ver o que come RAM
# 3) jq        - canivete de JSON que o Claude usa direto
# 4) sysctl    - ensina o kernel a usar a swap comprimida (zram) sem medo
set -e
apt-get install -y earlyoom btop jq
systemctl enable --now earlyoom
printf 'vm.swappiness=150\nvm.page-cluster=0\n' > /etc/sysctl.d/99-zram.conf
sysctl -p /etc/sysctl.d/99-zram.conf
echo
echo "=== VERIFICACAO ==="
systemctl is-active earlyoom
cat /proc/sys/vm/swappiness
echo "TUDO OK"
