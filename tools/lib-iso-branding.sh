#!/usr/bin/env bash
set -Eeuo pipefail

limad_iso_volume_id() {
  local version="$1" base suffix major minor patch suffix_id volid
  base="${version%%-*}"
  suffix="${version#"$base"}"
  IFS='.' read -r major minor patch <<< "$base"
  [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ && "$patch" =~ ^[0-9]+$ ]] || {
    echo "FATAL: unsupported LiMaD version for ISO label: $version" >&2
    return 1
  }
  volid="LIMAD_OS_${major}${minor}${patch}"
  if [[ -n "$suffix" ]]; then
    suffix_id="$(printf '%s' "${suffix#-}" | tr '[:lower:]' '[:upper:]' | sed -E 's/[^A-Z0-9]+/_/g; s/^_+|_+$//g')"
    [[ -n "$suffix_id" ]] && volid+="_${suffix_id}"
  fi
  [[ "${#volid}" -le 32 ]] || {
    echo "FATAL: ISO volume id exceeds 32 characters: $volid" >&2
    return 1
  }
  printf '%s\n' "$volid"
}

limad_system_area_has_hybrid_boot() {
  local report="$1"
  printf '%s\n' "$report" | grep -Eqi 'Boot record.*(MBR|GPT)|GPT partition|MBR partition'
}

limad_system_area_has_esp() {
  local report="$1" normalized
  normalized="$(printf '%s\n' "$report" | tr '[:upper:]' '[:lower:]' | tr -d '{}-')"

  if printf '%s\n' "$normalized" | grep -Eq     'gpt (partition )?type guid.*(c12a7328f81f11d2ba4b00a0c93ec93b|28732ac11ff8d211ba4b00a0c93ec93b)'; then
    return 0
  fi

  if printf '%s\n' "$normalized" | grep -Eq 'gpt partition path.*efiboot[.]img'; then
    return 0
  fi

  printf '%s\n' "$normalized" | grep -Eq 'mbr partition.*0x?ef([^0-9a-f]|$)'
}
