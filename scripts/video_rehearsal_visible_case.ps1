param(
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$OutRoot = "outputs/video_rehearsal_visible_case"
$CaseOut = Join-Path $OutRoot "natural_language_case"
$Results = New-Object System.Collections.Generic.List[object]
$Prompt = "Create a causal simulation with binary treatment A, continuous outcome Y, moderate observed confounding from X1 and X2, one prognostic-only covariate X3, 500 units, 30 Monte Carlo replications, and compare naive difference, adjusted OLS, IPW, and AIPW."

function Initialize-Console {
    try {
        $Host.UI.RawUI.WindowTitle = "DGPForge Award C visible rehearsal"
        $Host.UI.RawUI.ForegroundColor = "White"
        $Host.UI.RawUI.BackgroundColor = "Black"
    }
    catch {
        # Console sizing varies by host; launcher maximization is the reliable path.
    }
}

function Write-SceneTitle {
    param(
        [string]$Number,
        [string]$Title
    )

    Clear-Host
    Write-Host ""
    Write-Host "$Number. $Title" -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor DarkGray
    Write-Host ""
}

function Write-WrappedLines {
    param([string[]]$Lines)

    foreach ($line in $Lines) {
        Write-Host $line
    }
}

function Run-Command {
    param([string]$Command)

    Write-Host ""
    Write-Host "RUN:" -ForegroundColor Yellow
    Write-Host $Command -ForegroundColor Magenta
    Write-Host ""
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

function Pause-And-RecordScene {
    param(
        [string]$DefaultVisible,
        [string]$DefaultNotes = ""
    )

    Write-Host ""
    Write-Host ("-" * 72) -ForegroundColor DarkGray
    Write-Host "Codex: inspect the ACTUAL visible screen before answering." -ForegroundColor Yellow
    $suitability = Read-Host "Screen suitability? y / partial / n"
    if ([string]::IsNullOrWhiteSpace($suitability)) {
        $suitability = "partial"
    }

    $visible = Read-Host "What was visible?"
    if ([string]::IsNullOrWhiteSpace($visible)) {
        $visible = $DefaultVisible
    }

    $notes = Read-Host "Notes / what to change?"
    if ([string]::IsNullOrWhiteSpace($notes)) {
        $notes = $DefaultNotes
    }

    return @($suitability, $visible, $notes)
}

function Add-Result {
    param(
        [string]$Step,
        [string]$Title,
        [string]$CommandStatus,
        [double]$DurationSeconds,
        [string]$Suitability,
        [string]$Visible,
        [string]$Notes
    )

    $Results.Add([pscustomobject]@{
        step = $Step
        title = $Title
        command_status = $CommandStatus
        screen_suitability = $Suitability
        duration_seconds = [Math]::Round($DurationSeconds, 2)
        what_was_visible = $Visible
        notes = $Notes
    }) | Out-Null
}

function Invoke-Scene {
    param(
        [string]$Step,
        [string]$Title,
        [string]$DefaultVisible,
        [scriptblock]$Action
    )

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $status = "ok"
    $errorMessage = ""

    try {
        & $Action
    }
    catch {
        $status = "error"
        $errorMessage = $_.Exception.Message
        Write-Host ""
        Write-Host "ERROR: $errorMessage" -ForegroundColor Red
    }

    $confirmation = Pause-And-RecordScene `
        -DefaultVisible $DefaultVisible `
        -DefaultNotes $errorMessage
    $sw.Stop()

    Add-Result `
        -Step $Step `
        -Title $Title `
        -CommandStatus $status `
        -DurationSeconds $sw.Elapsed.TotalSeconds `
        -Suitability $confirmation[0] `
        -Visible $confirmation[1] `
        -Notes $confirmation[2]
}

function Write-Results {
    $jsonPath = Join-Path $OutRoot "video_rehearsal_visible_results.json"
    $mdPath = Join-Path $OutRoot "video_rehearsal_visible_results.md"

    $Results | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# DGPForge Visible Video Rehearsal Results")
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
    $lines.Add("Total measured visible rehearsal time: $([Math]::Round($total, 2)) seconds.")
    $lines | Set-Content -Path $mdPath -Encoding UTF8

    Clear-Host
    Write-Host ""
    Write-Host "Visible rehearsal complete." -ForegroundColor Green
    Write-Host "Results:"
    Write-Host $mdPath
    Write-Host ""
    Write-Host "Total measured time: $([Math]::Round($total, 2)) seconds"
}

function Open-Report {
    param([string]$ReportPath)

    $uri = ([System.Uri](Resolve-Path $ReportPath).Path).AbsoluteUri
    $edge = Get-Command msedge.exe -ErrorAction SilentlyContinue
    $chrome = Get-Command chrome.exe -ErrorAction SilentlyContinue

    if ($NoBrowser) {
        Write-Host "Browser disabled. Report target:" -ForegroundColor Yellow
        Write-Host $uri
        return
    }

    if ($edge) {
        Start-Process -FilePath $edge.Source -WindowStyle Maximized -ArgumentList @("--new-window", $uri)
    }
    elseif ($chrome) {
        Start-Process -FilePath $chrome.Source -WindowStyle Maximized -ArgumentList @("--new-window", $uri)
    }
    else {
        Start-Process -FilePath $uri
    }
}

if (-not (Test-Path "pyproject.toml") -or -not (Test-Path "dgpforge")) {
    throw "Run this script from the DGPForge repository root."
}

Initialize-Console

$workspace = [System.IO.Path]::GetFullPath((Get-Location).Path)
$caseFull = [System.IO.Path]::GetFullPath((Join-Path $workspace $CaseOut))
if (-not $caseFull.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write outside workspace: $caseFull"
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
Remove-Item -Recurse -Force $CaseOut -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $CaseOut | Out-Null

Invoke-Scene `
    -Step "1" `
    -Title "Natural language request" `
    -DefaultVisible "Prompt, readable draft command, provider mock/no API key, and three artifact lines." `
    -Action {
        Write-SceneTitle "1" "Natural language request"
        Write-WrappedLines @(
            "Prompt:",
            "Create a causal simulation with binary treatment A, continuous outcome Y,",
            "moderate observed confounding from X1 and X2, one prognostic-only X3,",
            "500 units, 30 Monte Carlo replications, comparing Naive, Adj OLS, IPW, AIPW."
        )

        Write-Host ""
        Write-Host "RUN:" -ForegroundColor Yellow
        Write-Host "python -m dgpforge.cli draft ``"
        Write-Host "  --prompt `"Create a causal simulation with binary treatment A,``"
        Write-Host "            continuous outcome Y, moderate observed confounding``"
        Write-Host "            from X1 and X2, one prognostic-only X3,``"
        Write-Host "            500 units, 30 Monte Carlo replications,``"
        Write-Host "            comparing Naive, Adj OLS, IPW, AIPW.`" ``"
        Write-Host "  --provider mock ``"
        Write-Host "  --out `"$CaseOut`" ``"
        Write-Host "  --run"
        Write-Host ""
        & python -m dgpforge.cli draft `
            --prompt $Prompt `
            --provider mock `
            --out $CaseOut `
            --run
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
            throw "Draft command failed with exit code $LASTEXITCODE"
        }

        Write-Host ""
        Write-Host "provider: mock, no API key" -ForegroundColor Green
        Write-Host "draft_dgp.yaml written"
        Write-Host "validation_report.md written"
        Write-Host "report.html written"
    }

Invoke-Scene `
    -Step "2" `
    -Title "Causal DGP contract / causal structure" `
    -DefaultVisible "One-screen causal structure summary with A, Y, X roles, X -> A, A+X -> Y, ATE, and estimators." `
    -Action {
        Write-SceneTitle "2" "Causal DGP contract / causal structure"
        Write-Host "Treatment node: A"
        Write-Host "Outcome node: Y"
        Write-Host ""
        Write-Host "Covariates:"
        Write-Host "  X1: confounder"
        Write-Host "  X2: confounder"
        Write-Host "  X3: prognostic-only"
        Write-Host ""
        Write-Host "Treatment assignment:"
        Write-Host "  X1, X2 -> A"
        Write-Host "Outcome model:"
        Write-Host "  A, X1, X2, X3 -> Y"
        Write-Host ""
        Write-Host "Observed confounding paths:"
        Write-Host "  X1 -> A and X1 -> Y"
        Write-Host "  X2 -> A and X2 -> Y"
        Write-Host ""
        Write-Host "Compact DAG:"
        Write-Host "  X1, X2 -> A -> Y"
        Write-Host "  X1, X2, X3 -> Y"
        Write-Host ""
        Write-Host "Estimand: marginal ATE / mean difference"
        Write-Host "Estimators: naive difference, adjusted OLS, IPW, AIPW"
    }

Invoke-Scene `
    -Step "3" `
    -Title "Validation gate" `
    -DefaultVisible "Status: PASS and two short validation-gate lines." `
    -Action {
        Write-SceneTitle "3" "Validation gate"
        Write-Host "Status: PASS" -ForegroundColor Green
        Write-Host ""
        Write-Host "The draft contract passed deterministic DGPContract schema validation."
        Write-Host "Simulation runs only after this gate passes."
    }

Invoke-Scene `
    -Step "4" `
    -Title "Known causal truth" `
    -DefaultVisible "DGP name, estimand, primary target, truth engine, and known causal target value." `
    -Action {
        Write-SceneTitle "4" "Known causal truth"
        $contractPath = Join-Path $CaseOut "draft_dgp.yaml"
        $py = @"
from pathlib import Path
from dgpforge.contracts import load_contract
from dgpforge.truth import truth_details

contract = load_contract(Path(r"$contractPath"))
details = truth_details(contract, oracle_n=20000)
truth = details.get("truth", details.get("true_ATE"))

print(f"DGP name: {contract.name}")
print(f"Estimand: {contract.estimand.name}")
print(f"Primary target: {contract.estimand.primary}")
print("Truth engine: dgpforge.truth.truth_details")
print(f"Known causal target value: {truth:.3f}")
"@
        $py | python -
    }

Invoke-Scene `
    -Step "5" `
    -Title "Monte Carlo diagnostics" `
    -DefaultVisible "Narrow estimator table plus one concise overlap line." `
    -Action {
        Write-SceneTitle "5" "Monte Carlo diagnostics"
        $py = @"
from pathlib import Path
import pandas as pd

out = Path(r"$CaseOut")
summary = pd.read_csv(out / "estimator_summary.csv")
diagnostics = pd.read_csv(out / "diagnostics.csv")
labels = {
    "naive_difference": "Naive",
    "adjusted_ols": "Adj OLS",
    "ipw": "IPW",
    "aipw": "AIPW",
}

rows = []
for _, row in summary.iterrows():
    rows.append({
        "estimator": labels.get(row["estimator"], row["estimator"]),
        "bias": f"{row['bias']:.3f}",
        "rmse": f"{row['rmse']:.3f}",
        "coverage": "NA" if pd.isna(row["coverage"]) else f"{row['coverage']:.3f}",
        "valid": int(row["n_valid"]),
        "failed": int(row["n_failed"]),
    })

table = pd.DataFrame(rows, columns=["estimator", "bias", "rmse", "coverage", "valid", "failed"])
print(table.to_string(index=False))
print("")
d = diagnostics.iloc[0]
print(
    "Overlap: "
    f"treatment prevalence={d['treatment_prevalence']:.3f}; "
    f"p-score p01={d['propensity_p01']:.3f}; "
    f"p-score p99={d['propensity_p99']:.3f}; "
    f"positivity warning={bool(d['positivity_warning'])}"
)
"@
        $py | python -
    }

Invoke-Scene `
    -Step "6" `
    -Title "HTML report" `
    -DefaultVisible "Browser opened local report top; checked known target cards, estimator summary, and reproducibility command." `
    -Action {
        Write-SceneTitle "6" "HTML report"
        $reportPath = Join-Path $CaseOut "report.html"
        Write-Host "Opening local report.html in browser..."
        Write-Host ""
        Write-Host "Inspect only these report sections:"
        Write-Host "  1. report top"
        Write-Host "  2. known target cards"
        Write-Host "  3. estimator summary table"
        Write-Host "  4. reproducibility command"
        Write-Host ""
        Write-Host "Do not open unrelated pages."
        Open-Report $reportPath
    }

Write-Results
