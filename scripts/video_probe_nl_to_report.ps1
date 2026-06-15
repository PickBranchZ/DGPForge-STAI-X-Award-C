param(
    [string]$OutRoot = "outputs/video_probe_nl_to_report",
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Results = New-Object System.Collections.Generic.List[object]

function Write-Rule {
    Write-Host ""
    Write-Host ("=" * 96) -ForegroundColor DarkGray
}

function Write-StepHeader {
    param(
        [string]$Id,
        [string]$Title,
        [string]$Goal,
        [string]$CodexAction
    )

    Write-Rule
    Write-Host "STEP $Id — $Title" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Goal:" -ForegroundColor Yellow
    Write-Host $Goal
    Write-Host ""
    Write-Host "Codex action:" -ForegroundColor Green
    Write-Host $CodexAction
    Write-Rule
}

function Add-Result {
    param(
        [string]$Id,
        [string]$Title,
        [string]$CommandStatus,
        [double]$DurationSeconds,
        [string]$Confirmed,
        [string]$Notes
    )

    $Results.Add([pscustomobject]@{
        step = $Id
        title = $Title
        command_status = $CommandStatus
        duration_seconds = [Math]::Round($DurationSeconds, 2)
        confirmed_by_codex = $Confirmed
        notes = $Notes
    }) | Out-Null
}

function Confirm-Step {
    param(
        [string]$DefaultNote = ""
    )

    $confirmed = Read-Host "Could this step be completed as intended? Type y, n, or partial"
    if ([string]::IsNullOrWhiteSpace($confirmed)) {
        $confirmed = "partial"
    }

    $notes = Read-Host "Notes or failure reason"
    if ([string]::IsNullOrWhiteSpace($notes)) {
        $notes = $DefaultNote
    }

    return @($confirmed, $notes)
}

function Invoke-ProbeStep {
    param(
        [string]$Id,
        [string]$Title,
        [string]$Goal,
        [string]$CodexAction,
        [scriptblock]$Action
    )

    Write-StepHeader -Id $Id -Title $Title -Goal $Goal -CodexAction $CodexAction

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $commandStatus = "ok"
    $errorMessage = ""

    try {
        & $Action
    }
    catch {
        $commandStatus = "error"
        $errorMessage = $_.Exception.Message
        Write-Host ""
        Write-Host "ERROR: $errorMessage" -ForegroundColor Red
    }

    $sw.Stop()

    $confirmation = Confirm-Step -DefaultNote $errorMessage
    Add-Result `
        -Id $Id `
        -Title $Title `
        -CommandStatus $commandStatus `
        -DurationSeconds $sw.Elapsed.TotalSeconds `
        -Confirmed $confirmation[0] `
        -Notes $confirmation[1]
}

function Run-Command {
    param([string]$Command)

    Write-Host ""
    Write-Host "PS> $Command" -ForegroundColor Magenta
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command"
    }
}

function Show-FileHead {
    param(
        [string]$Path,
        [int]$Lines = 40
    )

    if (-not (Test-Path $Path)) {
        throw "Missing expected file: $Path"
    }

    Write-Host ""
    Write-Host "Showing first $Lines lines of $Path" -ForegroundColor DarkCyan
    Write-Host ("-" * 96) -ForegroundColor DarkGray
    Get-Content $Path -TotalCount $Lines
    Write-Host ("-" * 96) -ForegroundColor DarkGray
}

function Open-Target {
    param([string]$Target)

    if ($NoBrowser) {
        Write-Host "Browser disabled. Target would be: $Target" -ForegroundColor DarkYellow
    }
    else {
        Start-Process $Target
    }
}

function Write-ProbeReport {
    param([string]$OutRoot)

    $jsonPath = Join-Path $OutRoot "video_probe_results.json"
    $mdPath = Join-Path $OutRoot "video_probe_results.md"

    $Results | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# DGPForge Video Probe Results")
    $lines.Add("")
    $lines.Add("Flow: natural language → DGP contract → validation → known truth → Monte Carlo diagnostics → report")
    $lines.Add("")
    $lines.Add("| Step | Title | Command status | Confirmed | Duration seconds | Notes |")
    $lines.Add("| --- | --- | --- | --- | ---: | --- |")

    foreach ($item in $Results) {
        $safeNotes = ($item.notes -replace "\|", "\|") -replace "`r?`n", " "
        $lines.Add("| $($item.step) | $($item.title) | $($item.command_status) | $($item.confirmed_by_codex) | $($item.duration_seconds) | $safeNotes |")
    }

    $lines.Add("")
    $lines.Add("Use this probe to decide which steps are reliable enough for an optional future walkthrough.")
    $lines | Set-Content -Path $mdPath -Encoding UTF8

    Write-Host ""
    Write-Host "Wrote probe reports:" -ForegroundColor Green
    Write-Host $jsonPath
    Write-Host $mdPath
}

# Ensure repo root.
if (-not (Test-Path "pyproject.toml") -or -not (Test-Path "dgpforge")) {
    throw "Run this script from the DGPForge repository root."
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

$DraftOut = Join-Path $OutRoot "natural_language_case"
Remove-Item -Recurse -Force $DraftOut -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $DraftOut | Out-Null

$Prompt = "Create a simulation with binary treatment, continuous outcome, moderate observed confounding, 500 units, 30 Monte Carlo replications, and compare naive difference, adjusted OLS, IPW, and AIPW."

Invoke-ProbeStep `
    -Id "0" `
    -Title "Environment check" `
    -Goal "Confirm the repo root, Python, package import, and CLI are available before the actual demo flow." `
    -CodexAction "Keep PowerShell visible. Confirm that these checks run without error." `
    -Action {
        Run-Command "python --version"
        Run-Command "python -c `"import dgpforge; print('dgpforge import ok')`""
        Run-Command "python -m dgpforge.cli --help"
    }

if (-not $SkipInstall) {
    Invoke-ProbeStep `
        -Id "0b" `
        -Title "Editable install check" `
        -Goal "Confirm a fresh viewer can install the project with dev extras." `
        -CodexAction "Run the install check. If the package is already installed, this should be quick." `
        -Action {
            Run-Command "python -m pip install -e `".[dev]`""
        }
}

Invoke-ProbeStep `
    -Id "1" `
    -Title "Natural language to DGP workflow" `
    -Goal "Use the optional mock LLM provider to convert a natural-language study request into a validated DGP workflow." `
    -CodexAction "Run the draft command. Confirm that it writes a report path and does not ask for an API key." `
    -Action {
        $cmd = "python -m dgpforge.cli draft --prompt `"$Prompt`" --provider mock --out `"$DraftOut`" --run"
        Run-Command $cmd
    }

Invoke-ProbeStep `
    -Id "2" `
    -Title "DGP contract artifact" `
    -Goal "Show that the natural-language prompt produced a concrete YAML DGP contract." `
    -CodexAction "Display the first part of draft_dgp.yaml. Check whether template, sample sizes, treatment, outcome, estimand, and estimators are visible." `
    -Action {
        Show-FileHead (Join-Path $DraftOut "draft_dgp.yaml") 80
    }

Invoke-ProbeStep `
    -Id "3" `
    -Title "Validation gate" `
    -Goal "Show deterministic schema validation before statistical execution." `
    -CodexAction "Display validation_report.md. Confirm it says PASS." `
    -Action {
        Show-FileHead (Join-Path $DraftOut "validation_report.md") 40
    }

Invoke-ProbeStep `
    -Id "4" `
    -Title "Known truth calculation" `
    -Goal "Load the generated DGP contract and print the known target used for benchmarking estimators." `
    -CodexAction "Keep PowerShell visible. Confirm that the printed truth details are understandable on screen." `
    -Action {
        $contractPath = Join-Path $DraftOut "draft_dgp.yaml"
        $py = @"
from pathlib import Path
from dgpforge.contracts import load_contract
from dgpforge.truth import truth_details

contract = load_contract(Path(r"$contractPath"))
details = truth_details(contract, oracle_n=20000)

print("DGP name:", contract.name)
print("Template:", contract.template)
print("Sample sizes:", contract.sample_sizes)
print("Monte Carlo replications:", contract.n_replications)
print("Estimators:", ", ".join(contract.estimators))
print("")
print("Known truth details:")
for key, value in details.items():
    print(f"  {key}: {value}")
"@
        $py | python -
    }

Invoke-ProbeStep `
    -Id "5" `
    -Title "Monte Carlo diagnostics" `
    -Goal "Show estimator bias/RMSE/coverage and diagnostic summaries generated from the known-truth Monte Carlo run." `
    -CodexAction "Keep PowerShell visible. Confirm the estimator summary and diagnostics tables fit on screen or can be scrolled." `
    -Action {
        $summaryPath = Join-Path $DraftOut "estimator_summary.csv"
        $diagnosticsPath = Join-Path $DraftOut "diagnostics.csv"

        $py = @"
from pathlib import Path
import pandas as pd

out = Path(r"$DraftOut")
summary = pd.read_csv(out / "estimator_summary.csv")
diagnostics = pd.read_csv(out / "diagnostics.csv")

summary_cols = [
    "sample_size", "estimator", "mean_estimate", "bias", "rmse",
    "coverage", "mcse_bias", "n_valid", "n_failed", "failure_rate"
]
summary_cols = [col for col in summary_cols if col in summary.columns]

diagnostic_cols = [
    "sample_size", "treatment_prevalence", "propensity_p01",
    "propensity_p99", "propensity_overlap_width", "positivity_warning"
]
diagnostic_cols = [col for col in diagnostic_cols if col in diagnostics.columns]

print("Estimator summary:")
print(summary[summary_cols].to_string(index=False))
print("")
print("Diagnostics:")
print(diagnostics[diagnostic_cols].to_string(index=False))
"@
        $py | python -
    }

Invoke-ProbeStep `
    -Id "6" `
    -Title "HTML report" `
    -Goal "Open the generated report and verify it visually presents known truth, Monte Carlo estimator behavior, diagnostics, and reproducibility command." `
    -CodexAction "Open report.html. In the browser, show the top of the report, then slowly scroll to the estimator summary table. Return to PowerShell and confirm whether this was easy to capture." `
    -Action {
        $reportPath = Resolve-Path (Join-Path $DraftOut "report.html")
        Open-Target $reportPath.Path
        Read-Host "After viewing the report in browser, return here and press Enter"
    }

Write-ProbeReport -OutRoot $OutRoot

Write-Rule
Write-Host "Probe complete." -ForegroundColor Green
Write-Host "Output directory: $OutRoot"
Write-Host "Review: $OutRoot\video_probe_results.md"
Write-Rule
