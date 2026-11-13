#!/usr/bin/env bash
# 每个交易日收盘后，把 A 股日线增量同步进本地 zvt 库。
# 由 crontab 调用：工作日 15:30。若当日仍无数据（数据源延迟/休市），20 分钟自动重试一次。
set -uo pipefail

HOME_DIR="/home/ubuntu"
PY="$HOME_DIR/.hermes/hermes-agent/venv/bin/python"
DB="$HOME_DIR/zvt-home/data/em/em_stock_1d_hfq_kdata.db"
LOG_DIR="$HOME_DIR/zvt-home/logs"
LOG="$LOG_DIR/zvt-sync-$(date +%Y-%m).log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

count_today() {
  "$PY" -c "
import sqlite3, datetime, os
db = os.path.expanduser('~/zvt-home/data/em/em_stock_1d_hfq_kdata.db')
if not os.path.isfile(db):
    print(-1); raise SystemExit
con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
print(con.execute('select count(*) from stock_1d_hfq_kdata where timestamp >= ?',
                  (datetime.date.today().isoformat(),)).fetchone()[0])
" 2>/dev/null || echo -1
}

# --check：只做体检，不写库（用于部署后验证）
if [ "${1:-}" = "--check" ]; then
  status="missing"; [ -f "$DB" ] && status="ok"
  echo "db=$status today_rows=$(count_today) log=$LOG"
  exit 0
fi

cd "$HOME_DIR/zvt-home" || exit 1
log "===== sync start ====="

for attempt in 1 2; do
  log "attempt $attempt: incremental_sync.py"
  timeout 3600 "$PY" incremental_sync.py >> "$LOG" 2>&1
  rc=$?
  rows=$(count_today)
  log "attempt $attempt done rc=$rc today_rows=$rows"

  if [ "$rows" -gt 0 ] 2>/dev/null; then
    break
  fi
  if [ "$attempt" = "1" ]; then
    log "当日无数据（数据源延迟或休市），20 分钟后再试一次"
    sleep 1200
  fi
done

# 日志超过 5MB 归档一份，避免无限增长
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 5000000 ]; then
  mv "$LOG" "$LOG.1"
fi

log "===== sync end ====="
exit 0
