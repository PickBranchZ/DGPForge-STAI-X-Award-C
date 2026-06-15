param(
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$OutRoot = "outputs/video_rehearsal_nl_to_report"
$CaseOut = Join-Path $OutRoot "natural_language_case"
$Prompt = "Create a causal simulation with binary treatment A, continuous outcome Y, moderate observed confounding from X1 and X2, one prognostic-only covariate X3, 500 units, 30 Monte Carlo replications, and compare naive difference, adjusted OLS, IPW, and AIPW."
$Results = New-Object System.Collections.Generic.List[object]

function Write-Rule {
    Write-Host ""
    Write-Host ("=" * 88) -ForegroundColor DarkGray
}

function Write-StepHeader {
    param(
        [string]$Id,
        [string]$Title
    )

    Write-Rule
    Write-Host "STEP $Id - $Title" -ForegroundColor Cyan
    Write-Rule
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

function Escape-MarkdownCell {
    param([string]$Value)

    if ($null -eq $Value) {
        return ""
    }
    return (($Value -replace "\|", "\|") -replace "`r?`n", " ")
}

function Add-Result {
    param(
        [string]$Id,
        [string]$Title,
        [string]$CommandStatus,
        [double]$DurationSeconds,
        [string]$Suitability,
        [string]$Visible,
        [string]$Notes
    )

    $Results.Add([pscustomobject]@{
        step = $Id
        title = $Title
        command_status = $CommandStatus
        screen_suitability = $Suitability
        duration_seconds = [Math]::Round($DurationSeconds, 2)
        what_was_visible = $Visible
        notes = $Notes
    }) | Out-Null
}

function Confirm-Screen {
    param(
        [string]$DefaultVisible,
        [string]$DefaultNote = ""
    )

    Write-Host ""
    Write-Host "Visible target:" -ForegroundColor Yellow
    Write-Host $DefaultVisible
    $suitability = Read-Host "Screen suitability for optional walkthrough? Type y, partial, or n"
    if ([string]::IsNullOrWhiteSpace($suitability)) {
        $suitability = "partial"
    }

    $notes = Read-Host "Notes or exact change needed"
    if ([string]::IsNullOrWhiteSpace($notes)) {
        $notes = $DefaultNote
    }

    return @($suitability, $notes)
}

function Invoke-RehearsalStep {
    param(
        [string]$Id,
        [string]$Title,
        [string]$Visible,
        [scriptblock]$Action
    )

    Write-StepHeader -Id $Id -Title $Title

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

    $confirmation = Confirm-Screen -DefaultVisible $Visible -DefaultNote $errorMessage
    $sw.Stop()

    Add-Result `
        -Id $Id `
        -Title $Title `
        -CommandStatus $commandStatus `
        -DurationSeconds $sw.Elapsed.TotalSeconds `
        -Suitability $confirmation[0] `
        -Visible $Visible `
        -Notes $confirmation[1]
}

function Write-RehearsalReport {
    param([string]$Root)

    $jsonPath = Join-Path $Root "video_rehearsal_results.json"
    $mdPath = Join-Path $Root "video_rehearsal_results.md"

    $Results | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# DGPForge Video Rehearsal Results")
    $lines.Add("")
    $lines.Add("Flow: natural language -> causal DGP contract -> validation -> known causal truth -> Monte Carlo diagnostics -> report")
    $lines.Add("")
    $lines.Add("| Step | Title | Command status | Screen suitability | Duration seconds | What was visible | Notes |")
    $lines.Add("| --- | --- | --- | --- | ---: | --- | --- |")

    foreach ($item in $Results) {
        $visible = Escape-MarkdownCell $item.what_was_visible
        $notes = Escape-MarkdownCell $item.notes
        $lines.Add("| $($item.step) | $($item.title) | $($item.command_status) | $($item.screen_suitability) | $($item.duration_seconds) | $visible | $notes |")
    }

    $total = ($Results | Measure-Object -Property duration_seconds -Sum).Sum
    $lines.Add("")
    $lines.Add("Total measured rehearsal time: $([Math]::Round($total, 2)) seconds.")
    $lines.Add("")
    $lines.Add("Use this rehearsal to decide which scenes are visually suitable for an optional future walkthrough.")
    $lines | Set-Content -Path $mdPath -Encoding UTF8

    Write-Host ""
    Write-Host "Wrote rehearsal reports:" -ForegroundColor Green
    Write-Host $jsonPath
    Write-Host $mdPath
}

if (-not (Test-Path "pyproject.toml") -or -not (Test-Path "dgpforge")) {
    throw "Run this script from the DGPForge repository root."
}

if (-not $SkipInstall) {
    Write-Host "SkipInstall was not supplied. This rehearsal assumes the environment is already ready." -ForegroundColor DarkYellow
}

$workspace = [System.IO.Path]::GetFullPath((Get-Location).Path)
$caseFull = [System.IO.Path]::GetFullPath((Join-Path $workspace $CaseOut))
if (-not $caseFull.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write outside workspace: $caseFull"
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
Remove-Item -Recurse -Force $CaseOut -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $CaseOut | Out-Null

Invoke-RehearsalStep `
    -Id "1" `
    -Title "Natural language request" `
    -Visible "Prompt, provider=mock/no API key, draft command, and concise artifact list." `
    -Action {
        Write-Host "Natural-language request:" -ForegroundColor Yellow
        Write-Host $Prompt
        Write-Host ""
        Write-Host "Provider: mock (deterministic; no API key required)"
        Write-Host "Output: $CaseOut"

        $cmd = "python -m dgpforge.cli draft --prompt `"$Prompt`" --provider mock --out `"$CaseOut`" --run"
        Run-Command $cmd

        Write-Host ""
        Write-Host "Artifacts written:" -ForegroundColor Green
        foreach ($name in @("draft_dgp.yaml", "validation_report.md", "report.html", "estimator_summary.csv", "diagnostics.csv", "reproduce.md", "contract.yaml")) {
            $path = Join-Path $CaseOut $name
            if (Test-Path $path) {
                Write-Host " - $name"
            }
        }
    }

Invoke-RehearsalStep `
    -Id "2" `
    -Title "Causal DGP contract" `
    -Visible "One-screen causal structure summary: A, Y, covariate roles, X -> A, A + X -> Y, confounders, estimand, estimators." `
    -Action {
        $contractPath = Join-Path $CaseOut "draft_dgp.yaml"
        $py = @"
from pathlib import Path
import yaml

cfg = yaml.safe_load(Path(r"$contractPath").read_text())
covariates = cfg.get("covariates", {})
treatment = cfg.get("treatment", {})
outcome = cfg.get("outcome", {})
estimand = cfg.get("estimand", {})

treatment_node = treatment.get("name", "A")
outcome_node = outcome.get("name", "Y")
treatment_formula = treatment.get("formula", {})
treatment_covs = [k for k in treatment_formula if k != "intercept"]
outcome_coeffs = outcome.get("coefficients", {})
outcome_covs = [k for k in outcome_coeffs if k != "intercept"]
confounders = [x for x in treatment_covs if x in outcome_covs]
prognostic_only = [x for x in outcome_covs if x not in treatment_covs]
roles = "; ".join(f"{name}={spec.get('role', 'unspecified')}" for name, spec in covariates.items())

def join(items):
    return ", ".join(items) if items else "none"

print("CAUSAL DGP CONTRACT SUMMARY")
print(f"Treatment node: {treatment_node}")
print(f"Outcome node: {outcome_node}")
print(f"Covariates and roles: {roles}")
print(f"Treatment assignment: {join(treatment_covs)} -> {treatment_node}")
print(f"Outcome model: {treatment_node} + {join(outcome_covs)} -> {outcome_node}")
print(f"Observed confounders: {join(confounders)}")
print(f"Prognostic-only covariates: {join(prognostic_only)}")

dag_bits = []
if confounders:
    dag_bits.append(f"{join(confounders)} -> {treatment_node} -> {outcome_node}")
    dag_bits.append(f"{join(confounders)} -> {outcome_node}")
if prognostic_only:
    dag_bits.append(f"{join(prognostic_only)} -> {outcome_node}")
print("Compact DAG reading: " + "; ".join(dag_bits))

print(f"Estimand: {estimand.get('name', 'unknown')} ({estimand.get('contrast', 'unknown contrast')})")
print("Estimators: " + ", ".join(cfg.get("estimators", [])))
"@
        $py | python -
    }

Invoke-RehearsalStep `
    -Id "3" `
    -Title "Validation gate" `
    -Visible "Status: PASS plus two short lines explaining deterministic schema validation before simulation." `
    -Action {
        $validationPath = Join-Path $CaseOut "validation_report.md"
        if (-not (Test-Path $validationPath)) {
            throw "Missing validation report: $validationPath"
        }

        $statusLine = Get-Content $validationPath | Where-Object { $_ -match "^Status:" } | Select-Object -First 1
        Write-Host $statusLine -ForegroundColor Green
        Write-Host "DGPContract schema validation must pass before statistical execution."
        Write-Host "The mock LLM drafts the contract; deterministic modules produce the evidence."
    }

Invoke-RehearsalStep `
    -Id "4" `
    -Title "Known causal truth" `
    -Visible "DGP name, estimand, primary target, truth engine, and known causal target value." `
    -Action {
        $contractPath = Join-Path $CaseOut "draft_dgp.yaml"
        $py = @"
from pathlib import Path
from dgpforge.contracts import load_contract
from dgpforge.truth import truth_details

contract = load_contract(Path(r"$contractPath"))
details = truth_details(contract, oracle_n=20000)
truth = details.get("truth", details.get("true_ATE"))

print("KNOWN CAUSAL TRUTH")
print(f"DGP name: {contract.name}")
print(f"Estimand: {contract.estimand.name}")
print(f"Primary target: {contract.estimand.primary}")
print("Truth engine: dgpforge.truth.truth_details (oracle_n=20000)")
print(f"Known causal target value: {truth:.3f}")
"@
        $py | python -
    }

Invoke-RehearsalStep `
    -Id "5" `
    -Title "Monte Carlo diagnostics" `
    -Visible "Narrow estimator table with estimator, bias, rmse, coverage, n_valid, n_failed plus one overlap diagnostics line." `
    -Action {
        $py = @"
from pathlib import Path
import pandas as pd

out = Path(r"$CaseOut")
summary = pd.read_csv(out / "estimator_summary.csv")
diagnostics = pd.read_csv(out / "diagnostics.csv")

cols = ["estimator", "bias", "rmse", "coverage", "n_valid", "n_failed"]
table = summary[cols].copy()
for col in ["bias", "rmse", "coverage"]:
    table[col] = table[col].map(lambda x: "NA" if pd.isna(x) else f"{x:.3f}")
for col in ["n_valid", "n_failed"]:
    table[col] = table[col].astype(int)

print("MONTE CARLO ESTIMATOR DIAGNOSTICS")
print(table.to_string(index=False))
print("")
d = diagnostics.iloc[0]
print(
    "Overlap diagnostics: "
    f"treatment_prevalence={d['treatment_prevalence']:.3f}; "
    f"propensity_p01={d['propensity_p01']:.3f}; "
    f"propensity_p99={d['propensity_p99']:.3f}; "
    f"positivity_warning={bool(d['positivity_warning'])}"
)
"@
        $py | python -
    }

Invoke-RehearsalStep `
    -Id "6" `
    -Title "HTML report" `
    -Visible "Generated local report top, known target cards, estimator summary table, and reproducibility section." `
    -Action {
        $reportPath = Resolve-Path (Join-Path $CaseOut "report.html")
        Write-Host "Opening local report:" -ForegroundColor Yellow
        Write-Host $reportPath.Path
        Write-Host "Recording target: report top -> known target cards -> estimator summary -> reproducibility."
        if ($NoBrowser) {
            Write-Host "Browser disabled. Inspect manually: $($reportPath.Path)" -ForegroundColor DarkYellow
        }
        else {
            Start-Process $reportPath.Path
        }
        Read-Host "Inspect the generated local report, then press Enter to continue"
    }

Write-RehearsalReport -Root $OutRoot

Write-Rule
Write-Host "Rehearsal complete." -ForegroundColor Green
Write-Host "Output directory: $OutRoot"
Write-Host "Review: $OutRoot\video_rehearsal_results.md"
Write-Rule
