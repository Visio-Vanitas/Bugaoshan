#!/bin/bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: $0 APP ENTITLEMENTS PROFILE IDENTITY EXPECTED_BUNDLE_ID" >&2
  exit 64
fi

app_path=$1
entitlements_path=$2
profile_path=$3
identity=$4
expected_bundle_id=$5

actual_bundle_id=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' \
  "$app_path/Contents/Info.plist")
if [[ "$actual_bundle_id" != "$expected_bundle_id" ]]; then
  echo "unexpected bundle ID: $actual_bundle_id" >&2
  exit 1
fi

profile_plist=$(mktemp "${TMPDIR:-/tmp}/bugaoshan-profile.XXXXXX.plist")
trap 'rm -f "$profile_plist"' EXIT
security cms -D -i "$profile_path" -o "$profile_plist"
profile_app_id=$(/usr/libexec/PlistBuddy \
  -c 'Print :Entitlements:com.apple.application-identifier' "$profile_plist")
if [[ "$profile_app_id" != "2F6UXH5569.$expected_bundle_id" ]]; then
  echo "Developer ID profile does not match $expected_bundle_id" >&2
  exit 1
fi

cp "$profile_path" "$app_path/Contents/embedded.provisionprofile"

if [[ -d "$app_path/Contents/Frameworks" ]]; then
  while IFS= read -r -d '' binary; do
    codesign --force --timestamp --options runtime --sign "$identity" "$binary"
  done < <(find "$app_path/Contents/Frameworks" -type f \
    \( -name '*.dylib' -o -name '*.so' \) -print0)

  while IFS= read -r framework; do
    codesign --force --timestamp --options runtime --sign "$identity" "$framework"
  done < <(find "$app_path/Contents/Frameworks" -depth -type d -name '*.framework')
fi

if [[ -d "$app_path/Contents/PlugIns" ]]; then
  while IFS= read -r bundle; do
    codesign --force --timestamp --options runtime --sign "$identity" "$bundle"
  done < <(find "$app_path/Contents/PlugIns" -depth -type d \
    \( -name '*.appex' -o -name '*.xpc' -o -name '*.app' \))
fi

codesign --force --timestamp --options runtime \
  --entitlements "$entitlements_path" --sign "$identity" "$app_path"
codesign --verify --deep --strict --verbose=2 "$app_path"

signed_team=$(codesign -d --verbose=4 "$app_path" 2>&1 \
  | sed -n 's/^TeamIdentifier=//p')
if [[ "$signed_team" != "2F6UXH5569" ]]; then
  echo "unexpected signing team: $signed_team" >&2
  exit 1
fi

sandbox=$(
  codesign -d --entitlements :- "$app_path" 2>/dev/null \
    | plutil -extract com.apple.security.app-sandbox raw -o - -
)
if [[ "$sandbox" != "true" ]]; then
  echo "app sandbox entitlement is missing" >&2
  exit 1
fi
