param(
    [switch]$SkipFrontend,
    [switch]$SkipJava,
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Get-ToolCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($env:OS -eq "Windows_NT") {
        $WindowsCommand = Get-Command "$Name.cmd" -ErrorAction SilentlyContinue
        if ($WindowsCommand) {
            return $WindowsCommand.Source
        }
    }

    $Command = Get-Command $Name -ErrorAction Stop
    return $Command.Source
}

function Invoke-VerifyStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Command
    Write-Host "==> $Name completed"
}

if (-not $SkipFrontend) {
    Invoke-VerifyStep "frontend-web: npm build" {
        Push-Location (Join-Path $RepoRoot "frontend-web")
        try {
            $Npm = Get-ToolCommand "npm"
            & $Npm ci
            & $Npm run build
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipJava) {
    Invoke-VerifyStep "backend-java: maven test" {
        Push-Location (Join-Path $RepoRoot "backend-java")
        try {
            $Maven = Get-ToolCommand "mvn"
            & $Maven -B test
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipPython) {
    Invoke-VerifyStep "backend-agent: ruff and pytest" {
        Push-Location (Join-Path $RepoRoot "backend-agent")
        try {
            $Python = Get-ToolCommand "python"
            $Ruff = Get-ToolCommand "ruff"
            $Pytest = Get-ToolCommand "pytest"

            & $Python -m pip install -e ".[dev]"
            & $Ruff check .
            & $Pytest
        }
        finally {
            Pop-Location
        }
    }
}

Write-Host ""
Write-Host "All requested verification steps completed."
