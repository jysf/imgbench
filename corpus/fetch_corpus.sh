#!/usr/bin/env sh
# fetch_corpus.sh — optionally pull + subset the larger redistributable test
# sets so big originals aren't committed. POSIX sh; needs curl + unzip.
#
# Source: imagecompression.info "New Test Images" (redistributable, no-sell).
# Verify the license at the page before redistributing anything you fetch:
#   https://imagecompression.info/test_images/
#
# Usage:
#   ./fetch_corpus.sh            # download into ./_download, subset into ./images
#   DEST=images ./fetch_corpus.sh
#
# This script DOES NOT invent URLs. Set NEWTEST_URL to the exact ZIP URL you
# verified, then re-run. Without it, the script explains what to do and exits 0
# (so CI that runs it as a no-op stays green).

set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
DEST=${DEST:-"$HERE/images"}
DL="$HERE/_download"
mkdir -p "$DEST" "$DL"

if [ -z "${NEWTEST_URL:-}" ]; then
  cat <<'EOF'
fetch_corpus.sh: no NEWTEST_URL set.

To fetch the imagecompression.info "New Test Images" subset:
  1. Open https://imagecompression.info/test_images/ and confirm the license.
  2. Copy the exact ZIP URL you want.
  3. Re-run:  NEWTEST_URL="<that-url>" ./fetch_corpus.sh
  4. Convert/crop the chosen originals to the eight CORPUS.md slots, then run
     `bench corpus` to record their sha256s.

Nothing downloaded (this is the safe default).
EOF
  exit 0
fi

ZIP="$DL/newtest.zip"
echo "Downloading $NEWTEST_URL ..."
curl -L --fail -o "$ZIP" "$NEWTEST_URL"
echo "Extracting into $DL/newtest ..."
mkdir -p "$DL/newtest"
unzip -o "$ZIP" -d "$DL/newtest" >/dev/null

cat <<EOF
Downloaded + extracted to $DL/newtest.

Next (manual, by design — keeps the committed corpus intentional):
  - Pick 4 photos, convert/crop to the slots in CORPUS.md, place in $DEST.
  - Run:  bench corpus --corpus "$HERE/.."   # prints sha256 to paste back.
EOF
