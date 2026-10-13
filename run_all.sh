#!/bin/bash
# 背景常駐（TUNNEL=1 ./run_all.sh 才開 Cloudflare tunnel；本機目前因防火牆封鎖 7844 埠無法連線）
#：伺服器 + Cloudflare quick tunnel，當掉自動重啟。公開網址寫入 tunnel_url.txt
cd "$(dirname "$0")"
pkill -f "python3 server.py" ; pkill -f "cloudflared tunnel" ; pkill -f "ngrok http" ; sleep 1
(while true; do python3 server.py >> server.log 2>&1; sleep 3; done) &
[ "$TUNNEL" = 1 ] && (while true; do ~/bin/cloudflared tunnel --no-autoupdate --url http://localhost:8080 2>&1 | while read l; do echo "$l" >> tunnel.log; u=$(echo "$l" | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com'); [ -n "$u" ] && echo "$u" > tunnel_url.txt; done; sleep 5; done) &
# ngrok 固定網址（需先 ~/bin/ngrok config add-authtoken <TOKEN>）
NGROK_DOMAIN=${NGROK_DOMAIN:-swimsuit-ultimatum-caring.ngrok-free.dev}
[ "$NGROK" != 0 ] && grep -q authtoken ~/.config/ngrok/ngrok.yml 2>/dev/null && (while true; do ~/bin/ngrok http --url=$NGROK_DOMAIN 8080 --log ngrok.log --log-format logfmt >/dev/null 2>&1; sleep 10; done) &
