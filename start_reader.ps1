# 在留カードリーダー起動スクリプト
# PowerShell から起動する場合はこのファイルを実行してください。

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $python = "python"
}

try {
    & $python --version | Out-Null
} catch {
    Write-Host "Python が見つかりません。" -ForegroundColor Red
    Write-Host "Python 3.11 以上をインストールしてから、もう一度実行してください。"
    Read-Host "Enter キーで終了します"
    exit 1
}

& $python (Join-Path $PSScriptRoot "launch_reader.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "起動に失敗しました。上のメッセージを確認してください。" -ForegroundColor Red
    Read-Host "Enter キーで終了します"
    exit 1
}
