<#
.SYNOPSIS
Downloads and atomically stages the reviewed PP-OCRv6 ONNX recognizer.

.DESCRIPTION
This maintainer-only script uses pinned Hugging Face resolve URLs.  The application does
not call it and never downloads OCR assets at runtime.
#>
[CmdletBinding()]
param(
    [string]$AssetDirectory = ""
)

$ErrorActionPreference = "Stop"

# Resolve the default in the script body, not in the param() default.
# Windows PowerShell 5.1 does not populate $PSScriptRoot while binding parameter defaults,
# so the previous default threw "Cannot bind argument to parameter 'Path' because it is an
# empty string" before the script could run at all. 5.1 is still the default shell on
# Windows Server 2016, which this project supports.
if ([string]::IsNullOrWhiteSpace($AssetDirectory)) {
    $scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $AssetDirectory = Join-Path (Split-Path -Parent $scriptDirectory) "resources\ocr\ppocrv6"
}
$revision = "4ca479517810450af7bcff5bac0e6c4616987d51"
$modelHash = "9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba"
$baseUrl = "https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx/resolve/$revision"
$parent = Split-Path -Parent $AssetDirectory
$temporary = Join-Path $parent (".ppocrv6-stage-" + [guid]::NewGuid().ToString("N"))
$backup = ""

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Convert-YamlCharacter([string]$Value) {
    # Trim ASCII space, tab and CR only — never .NET's parameterless Trim(), which strips
    # *all* Unicode whitespace. Dictionary entry 1748 is U+3000 IDEOGRAPHIC SPACE, a real
    # character the recognizer must be able to emit; a bare Trim() silently turned it into
    # an empty string, producing a dictionary that differed from the reviewed manifest in
    # exactly one of 18,708 entries. YAML itself strips only space and tab from a plain
    # scalar, so this matches both the specification and PyYAML.
    $value = $Value.Trim(" `t`r".ToCharArray())
    if ($value.Length -ge 2 -and $value.StartsWith("'") -and $value.EndsWith("'")) {
        return $value.Substring(1, $value.Length - 2).Replace("''", "'")
    }
    if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
        # Windows PowerShell 5.1 has neither System.Text.Json nor PowerShell's generic
        # method-call syntax. The reviewed metadata uses ordinary YAML double-quoted
        # scalars only, so decode the YAML escapes directly and remain PS 5.1 compatible.
        $inner = $value.Substring(1, $value.Length - 2)
        return $inner.Replace('\\', '\').Replace('\"', '"')
    }
    return $value
}

try {
    New-Item -ItemType Directory -Force -Path $temporary | Out-Null
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/inference.onnx" -OutFile (Join-Path $temporary "model.onnx")
        Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/inference.yml" -OutFile (Join-Path $temporary "inference.yml")
    } catch {
        throw "Could not download pinned PP-OCRv6 assets. Check network access and retry. $($_.Exception.Message)"
    }
    if ((Get-FileSha256 (Join-Path $temporary "model.onnx")) -ne $modelHash) {
        throw "Downloaded inference.onnx does not match the reviewed SHA-256."
    }
    $lines = Get-Content -LiteralPath (Join-Path $temporary "inference.yml") -Encoding UTF8
    $insidePostProcess = $false; $insideDictionary = $false; $characters = [System.Collections.Generic.List[string]]::new()
    foreach ($line in $lines) {
        if ($line -match '^PostProcess:\s*$') { $insidePostProcess = $true; continue }
        if (-not $insidePostProcess) { continue }
        if ($line -match '^  character_dict:\s*$') { $insideDictionary = $true; continue }
        if ($insideDictionary -and $line -match '^  - (.*)$') { $characters.Add((Convert-YamlCharacter $matches[1])); continue }
        if ($insideDictionary -and $line -notmatch '^\s*$') { break }
    }
    if ($characters.Count -eq 0) { throw "inference.yml has no PostProcess.character_dict entries." }
    # Join with an explicit LF rather than using WriteAllLines, which emits
    # [Environment]::NewLine (CRLF on Windows). This artifact is checksum-verified, so its
    # bytes must not depend on the operating system that staged it.
    $dictionaryText = ($characters -join "`n") + "`n"
    [System.IO.File]::WriteAllText((Join-Path $temporary "dictionary.txt"), $dictionaryText, [System.Text.UTF8Encoding]::new($false))
    $manifest = [ordered]@{
        schema_version = 1
        model_name = "PP-OCRv6_medium_rec"
        source = "PaddlePaddle/PP-OCRv6_medium_rec_onnx"
        source_revision = $revision
        source_url = $baseUrl
        license = "Apache-2.0"
        model_file = "model.onnx"
        model_sha256 = Get-FileSha256 (Join-Path $temporary "model.onnx")
        metadata_file = "inference.yml"
        metadata_sha256 = Get-FileSha256 (Join-Path $temporary "inference.yml")
        dictionary_file = "dictionary.txt"
        dictionary_sha256 = Get-FileSha256 (Join-Path $temporary "dictionary.txt")
        image_mode = "BGR"
        input_dimensions = @(3, 48, 320)
        postprocess = "CTCLabelDecode"
        dictionary_entries = $characters.Count
    }
    # The committed manifest is the reviewed record, not this script's output. model.onnx is
    # not tracked in Git, so that file is the only thing standing between a staged download
    # and whatever the upstream host happens to serve. When one exists, every staged
    # artifact must reproduce it exactly or nothing is installed. This mirrors
    # tools/fetch_ocr_assets.py; the two tools must not diverge.
    $reviewedPath = Join-Path $AssetDirectory "manifest.json"
    if (Test-Path -LiteralPath $reviewedPath) {
        $reviewed = Get-Content -LiteralPath $reviewedPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $mismatches = @()
        foreach ($field in @("source_revision", "model_sha256", "metadata_sha256", "dictionary_sha256", "dictionary_entries", "model_name")) {
            $expected = $reviewed.$field
            if ($null -ne $expected -and "$expected" -ne "$($manifest[$field])") {
                $mismatches += "$field : manifest says '$expected', downloaded set produced '$($manifest[$field])'"
            }
        }
        if ($mismatches.Count -gt 0) {
            throw "The downloaded OCR assets do not match the reviewed manifest. Nothing was installed.`n  " + ($mismatches -join "`n  ")
        }
        # Keep the committed file byte-for-byte; rewriting it would leave a spurious diff
        # and would quietly make the download its own authority.
        Copy-Item -LiteralPath $reviewedPath -Destination (Join-Path $temporary "manifest.json") -Force
    } else {
        [System.IO.File]::WriteAllText((Join-Path $temporary "manifest.json"), ($manifest | ConvertTo-Json -Depth 4) + "`n", [System.Text.UTF8Encoding]::new($false))
    }
    if (Test-Path -LiteralPath $AssetDirectory) {
        $backup = "$AssetDirectory.backup-" + [guid]::NewGuid().ToString("N")
        Move-Item -LiteralPath $AssetDirectory -Destination $backup
    }
    Move-Item -LiteralPath $temporary -Destination $AssetDirectory
    if ($backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
    Write-Host "Staged verified PP-OCRv6 assets at $AssetDirectory"
} catch {
    if ($backup -and -not (Test-Path -LiteralPath $AssetDirectory) -and (Test-Path -LiteralPath $backup)) { Move-Item -LiteralPath $backup -Destination $AssetDirectory }
    throw
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
}
