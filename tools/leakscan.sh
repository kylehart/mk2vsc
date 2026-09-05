#!/usr/bin/env bash
# Refuse to ship identifying or secret material. Run before every push; CI runs it too.
set -u
cd "$(dirname "$0")/.."
pat='HQ2[0-9]{3}[A-Z0-9]{5}|c0619ab|idSite|TPWMBU|VRM_TOKEN|VRM_PASSWORD|password=|@getbetter|@ideascale|kapok|irie solar|tutton|railway\.app|guava|mango|papaya|sugar.?apple'
hits=$(grep -rIn -i -E "$pat" --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.pytest_cache --exclude-dir=__pycache__ --exclude-dir=fixtures --exclude-dir="*.egg-info" --exclude=leakscan.sh . || true)
manifest=$(grep -n -i -E "$pat" fixtures/manifest.json || true)
bin=$(grep -l -a -E "c0619ab|HQ2[0-9]{3}[A-Z0-9]{5}" fixtures/*/*.rvms 2>/dev/null || true)
names=$(find fixtures -iname "*guava*" -o -iname "*mango*" -o -iname "*papaya*" -o -iname "*sugar*" 2>/dev/null || true)
if [ -n "$hits$manifest$bin$names" ]; then echo "LEAK SCAN FAILED:"; echo "$hits"; echo "$manifest"; echo "$bin"; echo "$names"; exit 1; fi
echo "leak scan clean"
