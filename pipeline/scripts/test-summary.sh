#!/usr/bin/env bash
# Prints test totals from JUnit XML report directories (surefire, failsafe).
#   test-summary.sh <report-dir>...
# Exits 1 when any test failed or errored; 0 otherwise.
set -euo pipefail

[ "$#" -ge 1 ] || { echo "usage: test-summary.sh <report-dir>..." >&2; exit 2; }

total=0 failed=0 errored=0 skipped=0
for directory in "$@"; do
  shopt -s nullglob
  files=("${directory}"/TEST-*.xml)
  shopt -u nullglob
  if [ "${#files[@]}" -eq 0 ]; then
    echo "${directory}: no reports"
    continue
  fi
  run=0 bad=0 err=0 skip=0
  for file in "${files[@]}"; do
    header="$(grep -m1 -o '<testsuite [^>]*' "${file}")"
    run=$((run + $(grep -o ' tests="[0-9]*"' <<<"${header}" | grep -o '[0-9]*')))
    bad=$((bad + $(grep -o ' failures="[0-9]*"' <<<"${header}" | grep -o '[0-9]*')))
    err=$((err + $(grep -o ' errors="[0-9]*"' <<<"${header}" | grep -o '[0-9]*')))
    skip=$((skip + $(grep -o ' skipped="[0-9]*"' <<<"${header}" | grep -o '[0-9]*')))
  done
  printf '%s: %d tests, %d failed, %d errors, %d skipped\n' "${directory}" "${run}" "${bad}" "${err}" "${skip}"
  total=$((total + run)); failed=$((failed + bad)); errored=$((errored + err)); skipped=$((skipped + skip))
done
printf 'total: %d tests, %d failed, %d errors, %d skipped\n' "${total}" "${failed}" "${errored}" "${skipped}"
[ $((failed + errored)) -eq 0 ]
