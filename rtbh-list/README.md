sudo tee /usr/local/bin/cli-feed-update.sh << 'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
IPSET_NAME="cli-rtbh"
TMP_SET="${IPSET_NAME}-new"
FEED_URL="https://feed.cli.com.tr/robots.txt"
LOG="/var/log/cli-feed-update.log"

log() { echo "[$(date '+%Y-%m-%d %T')] $*" | tee -a "$LOG"; }

ipset create "$IPSET_NAME" hash:net maxelem 100000 family inet hashsize 4096 2>/dev/null || true

iptables -C INPUT   -m set --match-set "$IPSET_NAME" src -j DROP 2>/dev/null || \
iptables -I INPUT   -m set --match-set "$IPSET_NAME" src -j DROP
iptables -C FORWARD -m set --match-set "$IPSET_NAME" src -j DROP 2>/dev/null || \
iptables -I FORWARD -m set --match-set "$IPSET_NAME" src -j DROP

log "Feed indiriliyor..."
IPS=$(curl -sf --max-time 30 "$FEED_URL" | grep -E '^[0-9]' | grep -v '^#') || {
    log "HATA: Feed indirilemedi!"; exit 1
}

# ipset restore formatında toplu yükleme (subprocess döngüsü yok → çok daha hızlı)
{
    echo "create $TMP_SET hash:net maxelem 100000 family inet hashsize 4096"
    echo "$IPS" | awk -v s="$TMP_SET" '{print "add " s " " $1}'
} | ipset restore -exist

SAYI=$(ipset list "$TMP_SET" | grep -cE '^[0-9]' || echo 0)

ipset swap "$TMP_SET" "$IPSET_NAME"
ipset destroy "$TMP_SET"

log "Tamamlandı. Yüklenen kayıt: $SAYI"
SCRIPT

sudo chmod +x /usr/local/bin/cli-feed-update.sh

# Test et
sudo systemctl start cli-feed-update.service
sudo journalctl -u cli-feed-update.service -n 10

sudo tee /etc/systemd/system/cli-feed-update.service << 'EOF'
[Unit]
Description=CLI RTBH Feed Güncelleyici
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/cli-feed-update.sh
StandardOutput=journal
StandardError=journal
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now cli-feed-update.timer
# Kontrol
sudo systemctl list-timers cli-feed-update.timer
