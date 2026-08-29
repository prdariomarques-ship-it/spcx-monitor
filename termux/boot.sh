#!/data/data/com.termux/files/usr/bin/bash
# Coloque este arquivo em ~/.termux/boot/start-spcx-monitor.sh
# Instale o app Termux:Boot para que seja executado no boot do Android

sleep 10  # aguarda rede estabilizar

cd ~/spcx-monitor
mkdir -p logs
nohup python monitor_spcx.py >> logs/termux.out 2>&1 &
echo "[$(date)] spcx-monitor started, PID $!" >> logs/termux.out
