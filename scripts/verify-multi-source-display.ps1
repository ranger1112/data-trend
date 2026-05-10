$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host "== $Name"
    & $Command
}

Invoke-Step "Python tests" {
    & .\.venv\Scripts\python.exe -m pytest
}

Invoke-Step "Python lint" {
    & .\.venv\Scripts\python.exe -m ruff check apps packages tests migrations
}

Invoke-Step "Admin web build" {
    Push-Location admin-web
    try {
        npm run build
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Miniapp JSON parse" {
    Get-ChildItem miniapp -Recurse -Filter *.json | ForEach-Object {
        Get-Content -Raw -Path $_.FullName | ConvertFrom-Json | Out-Null
        Write-Host $_.FullName
    }
}

Invoke-Step "Miniapp JS syntax" {
    Get-ChildItem miniapp -Recurse -Filter *.js | ForEach-Object {
        node --check $_.FullName
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
}

Invoke-Step "Miniapp page smoke tests" {
    node --test miniapp/tests/page-smoke.test.js
}

Write-Host "== Automated verification complete"
Write-Host "Manual WeChat DevTools or device verification is still required by docs/multi-source-display-experience-plan.md."
