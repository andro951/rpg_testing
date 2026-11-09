#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
DOTNET="${DOTNET:-dotnet}"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
"$DOTNET" build --nologo --disable-build-servers
DLL=bin/Debug/net8.0/IntentParser.dll
"$DOTNET" "$DLL" self-test
for fixtures in fixtures/parity-fixtures.json fixtures/optional-parity-fixtures.json fixtures/shared-fixtures.json fixtures/current-revision-fixtures.json fixtures/current-contract-regressions.json robustness-parity-fixtures.json; do
  "$DOTNET" "$DLL" check "$fixtures"
done
