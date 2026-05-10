$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "miniapp"
$output = Join-Path $root ".tools\miniapp-preview-info.json"
$cli = "C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat"

if (-not (Test-Path $cli)) {
    throw "WeChat DevTools CLI not found: $cli"
}

if (-not (Test-Path $project)) {
    throw "Miniapp project not found: $project"
}

$outputDir = Split-Path -Parent $output
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if (Test-Path $output) {
    Remove-Item $output
}

Write-Host "== WeChat DevTools login status"
& $cli islogin --port 18344 --disable-gpu

Write-Host "== WeChat DevTools preview"
& $cli preview `
    --project $project `
    --port 18344 `
    --disable-gpu `
    --qr-format terminal `
    --info-output $output

if (-not (Test-Path $output)) {
    throw "Preview finished without generating info-output: $output"
}

Write-Host "== Preview info"
Get-Content -Raw $output
