param(
    [Parameter(Mandatory = $true)]
    [string]$OrchestratorPython,
    [Parameter(Mandatory = $true)]
    [string]$Runner,
    [Parameter(Mandatory = $true)]
    [string]$CaseRoot,
    [Parameter(Mandatory = $true)]
    [string]$TrainingPython,
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [Parameter(Mandatory = $true)]
    [string]$StatusFile
)

$ErrorActionPreference = 'Stop'
$exitCode = 1
try {
    & $OrchestratorPython $Runner execute `
        --case-root $CaseRoot `
        --training-python $TrainingPython `
        --output-root $OutputRoot
    $exitCode = $LASTEXITCODE
}
catch {
    Write-Error $_
    $exitCode = 1
}
finally {
    [System.IO.File]::WriteAllText(
        $StatusFile,
        "$exitCode`n",
        [System.Text.UTF8Encoding]::new($false)
    )
}
exit $exitCode
