#!/usr/bin/env bash
# R23R test sweep: run every standalone test_*.py at project root, in parallel,
# with a per-test timeout; collect pass/fail/skip into /tmp/sweep_results.txt.
cd "$(dirname "$0")"
export QT_QPA_PLATFORM=offscreen
export PYTHONDONTWRITEBYTECODE=1
rm -f /tmp/sweep_results.txt
ls test_*.py | sort | xargs -P 4 -I{} bash -c '
  f="{}"
  log="/tmp/sweep_logs/${f%.py}.log"
  mkdir -p /tmp/sweep_logs
  if timeout 300 python3 "$f" >"$log" 2>&1; then
    echo "PASS $f" >> /tmp/sweep_results.txt
  else
    rc=$?
    if [ "$rc" = "124" ]; then
      echo "TIMEOUT $f" >> /tmp/sweep_results.txt
    else
      echo "FAIL($rc) $f" >> /tmp/sweep_results.txt
    fi
  fi
'
echo "=== SWEEP DONE ==="
sort /tmp/sweep_results.txt | awk "{print \$1}" | uniq -c
grep -c "^PASS" /tmp/sweep_results.txt | xargs echo "passed:"
grep -v "^PASS" /tmp/sweep_results.txt || echo "(no failures)"
