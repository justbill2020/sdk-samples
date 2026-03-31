#!/bin/bash
# Every app should have the same version of cp.py. This test verifies a new
# app or modified app does not have an out-of-date copy.

reference_file="./cp.py"

if [[ ! -f "$reference_file" ]]; then
  echo "Missing reference file: $reference_file"
  exit 1
fi

for folder in ./*/; do
  app_file="${folder%/}/cp.py"
  if [[ -f "$app_file" ]]; then
    if ! cmp -s "$app_file" "$reference_file"; then
      echo "The cp.py file in ${folder%/} is not the correct version"
      exit 1
    fi
  fi
done
