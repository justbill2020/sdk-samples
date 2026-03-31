#!/bin/bash
# Every app should have the same version of csclient.py.
# This test verifies a new app or modified app does not have an out-of-date copy.
set -euo pipefail

reference=""
for candidate in "app_template/csclient.py" "app_template_csclient/csclient.py" "SimSelector/csclient.py"; do
        if [ -f "$candidate" ]; then
                reference="$candidate"
                break
        fi
done

if [ -z "$reference" ]; then
        echo "No reference csclient.py found; skipping csclient consistency check."
        exit 0
fi

for folder in ./*/; do
        if [ -f "${folder}csclient.py" ]; then
                file1="${folder}csclient.py"
                if ! cmp -s "$file1" "$reference"; then
                        echo "The csclient.py file in $folder is not the correct version (reference: $reference)."
                        exit 1
                fi
        fi
done
