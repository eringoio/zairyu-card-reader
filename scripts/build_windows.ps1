<#
.SYNOPSIS
    Build the Windows distribution of the local residence-card reader.

.DESCRIPTION
    Produces dist\zairyu-reader\zairyu-reader.exe, which runs on a Windows PC that has no
    Python installed. Requires a PC/SC-capable NFC reader driver at run time, not at build
    time.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -SkipTests
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$UseLockfile,
    [switch]$Package,
    [string]$Version = "0.2.1",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($Python)) {
    if (Test-Path ".venv\Scripts\python.exe") {
        $Python = ".venv\Scripts\python.exe"
    } else {
        $Python = "python"
    }
}

Write-Host "Using Python: $Python"
& $Python --version
if (-not $?) { throw "Python was not found. Install Python 3.11+ and retry." }

Write-Host "`n== Installing build and runtime dependencies =="
& $Python -m pip install --upgrade pip
if ($UseLockfile) {
    Write-Host "Installing the pinned, hash-verified dependency set."
    & $Python -m pip install --require-hashes -r requirements.lock.txt
    if (-not $?) { throw "Pinned dependency installation failed." }
} else {
    & $Python -m pip install -r requirements.txt
    if (-not $?) { throw "Dependency installation failed." }
}
& $Python -m pip install pyinstaller
if (-not $?) { throw "PyInstaller installation failed." }

Write-Host "`n== Verifying staged local OCR assets =="
& $Python tools\verify_ocr_assets.py
if (-not $?) { throw "The packaged PP-OCRv6 model is unavailable or failed checksum verification. Run tools\fetch_ocr_assets.ps1 before building." }

Write-Host "`n== Verifying packaged trust anchors =="
# Every certificate must match the SHA-256 recorded in the manifest before it is packaged.
# A trust anchor that fails here would ship as a silently unusable one.
& $Python -m pytest -q tests\test_packaged_assets_integrity.py
if (-not $?) { throw "Packaged trust-anchor or OCR asset integrity check failed. Do not build a release from this tree." }

Write-Host "`n== Verifying the local application health contract =="
& $Python -c "from app import health; assert health()['app'] == 'zairyu-reader'; print('health contract ok')"
if (-not $?) { throw "The local health contract check failed." }

if (-not $SkipTests) {
    Write-Host "`n== Running the test suite =="
    # Some locked-down Windows profiles deny pytest access to its default directory under
    # %LOCALAPPDATA%\Temp. Keep test scratch data in this ignored repository directory so
    # the release gate remains usable without weakening the test suite.
    & $Python -m pytest -q --basetemp=.pytest-tmp
    if (-not $?) { throw "Tests failed. Fix them before building a distribution." }
}

$node = Get-Command node -ErrorAction SilentlyContinue
if ($null -ne $node) {
    Write-Host "`n== Checking browser script syntax =="
    & node --check static\local.js
    if (-not $?) { throw "JavaScript syntax check failed." }
} else {
    Write-Host "`nNode.js was not found; skipped static\local.js syntax validation."
}

Write-Host "`n== Generating the original application icon =="
& $Python assets\generate_icon.py
if (-not $?) { throw "Application icon generation failed." }

Write-Host "`n== Cleaning previous build output =="
foreach ($path in @("build", "dist")) {
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
}

Write-Host "`n== Building zairyu-reader.exe =="
& $Python -m PyInstaller --clean --noconfirm zairyu-reader.spec
if (-not $?) { throw "PyInstaller build failed." }

$exe = Join-Path $repoRoot "dist\zairyu-reader\zairyu-reader.exe"
if (-not (Test-Path $exe)) { throw "Expected build output not found: $exe" }

Write-Host "`n== Verifying bundled runtime resources =="
$bundled = @(
    "dist\zairyu-reader\_internal\static\index.html",
    "dist\zairyu-reader\_internal\resources\ocr\ppocrv6\manifest.json",
    "dist\zairyu-reader\_internal\resources\ocr\ppocrv6\model.onnx",
    "dist\zairyu-reader\_internal\resources\ocr\ppocrv6\inference.yml",
    "dist\zairyu-reader\_internal\resources\ocr\ppocrv6\dictionary.txt",
    "dist\zairyu-reader\_internal\resources\moj\trust-anchors\manifest.json",
    "dist\zairyu-reader\_internal\webview"
)
foreach ($item in $bundled) {
    if (-not (Test-Path $item)) { throw "Missing bundled resource: $item" }
    Write-Host "  ok $item"
}

Write-Host "`n== Verifying no script payload is bundled =="
# The application must never hand a file to an external interpreter. If a .ps1 reappears
# in the bundle, an OCR or helper path that spawns PowerShell has been reintroduced.
$scripts = Get-ChildItem "dist\zairyu-reader" -Recurse -File -Include *.ps1, *.bat, *.cmd -ErrorAction SilentlyContinue
if ($null -ne $scripts) {
    $names = ($scripts | ForEach-Object { $_.FullName }) -join ", "
    throw "Unexpected script payload in the distribution: $names"
}
Write-Host "  ok no .ps1/.bat/.cmd payload in the bundle"

Write-Host "`n== Inspecting the distribution for material that must not ship =="
& $Python scripts\inspect_distribution.py "dist\zairyu-reader"
if (-not $?) { throw "Distribution inspection failed. Do not release this build." }

Write-Host "`n== Verifying packaged certificates survived packaging unchanged =="
# PyInstaller copies data files, but a build machine with the wrong Git line-ending
# settings, or a corrupted staging directory, would produce a bundle whose trust anchors
# no longer match their fingerprints. Check the packaged copies, not the source tree.
& $Python -c @"
import hashlib, json, sys
from pathlib import Path
root = Path('dist/zairyu-reader/_internal/resources/moj/trust-anchors')
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
bad = []
for entry in manifest['anchors']:
    packaged = Path('dist/zairyu-reader/_internal') / entry['path']
    if not packaged.is_file():
        bad.append(f\"missing {entry['anchor_id']}\")
        continue
    actual = ':'.join(f'{b:02X}' for b in hashlib.sha256(packaged.read_bytes()).digest())
    if actual != entry['sha256_fingerprint']:
        bad.append(f\"fingerprint mismatch {entry['anchor_id']}\")
print('\n'.join(bad) if bad else f'all {len(manifest[\"anchors\"])} packaged trust anchors verified')
sys.exit(1 if bad else 0)
"@
if (-not $?) { throw "Packaged trust anchors do not match their fingerprints." }

if ($Package) {
    Write-Host "`n== Creating the release archive =="
    $archive = "dist\zairyu-reader-$Version-windows-x64.zip"
    if (Test-Path $archive) { Remove-Item -Force $archive }
    Compress-Archive -Path "dist\zairyu-reader" -DestinationPath $archive -CompressionLevel Optimal
    if (-not (Test-Path $archive)) { throw "Archive creation failed." }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
    $name = Split-Path -Leaf $archive
    "$hash  $name" | Out-File -Encoding ascii "$archive.sha256"
    Write-Host "  $archive"
    Write-Host "  $archive.sha256"
    Write-Host "  SHA-256: $hash"
}

Write-Host "`nBuild complete: $exe"
$sizeBytes = (Get-ChildItem "dist\zairyu-reader" -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host ("Distribution size: {0:N1} MiB" -f ($sizeBytes / 1MB))

Write-Host "`n== IMPORTANT =="
Write-Host "Distribute the WHOLE dist\zairyu-reader folder. zairyu-reader.exe will not run"
Write-Host "without the _internal folder beside it."
Write-Host ""
Write-Host "This executable is UNSIGNED. Windows SmartScreen will warn on first run."
Write-Host "An unsigned binary is not trustworthy merely because its source is public:"
Write-Host "nothing ties this file to that source. Recipients who need assurance should"
Write-Host "build it themselves, or you should sign it with a real code-signing identity."
Write-Host "Verify the archive checksum against the one published with the release."
Write-Host "Staff launch:   double-click zairyu-reader.exe (WebView2 or Chromium app window)"
Write-Host "Chrome app mode: zairyu-reader.exe --chrome-app"
Write-Host "Force WebView2:   zairyu-reader.exe --webview"
Write-Host "Browser fallback: zairyu-reader.exe --browser"
Write-Host "Server only:    zairyu-reader.exe --no-browser (or legacy --headless)"
Write-Host "Windows Server 2016 prefers an installed Chrome/Edge/Chromium app window; WebView2 is not bundled."
Write-Host "Local reader settings are written to %APPDATA%\ZairyuReader; copy text remains in page memory and the Windows clipboard."
