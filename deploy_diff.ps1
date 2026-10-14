# Helper for deployGUI.bat
#
# Compares the files in -LocalDir against the manifest saved by the last
# successful deploy, and writes the relative paths of every new or changed
# file to -ListOut (one per line, for `tar -T`). A candidate manifest is
# written to "<Manifest>.new"; deployGUI.bat promotes it to -Manifest only
# after the transfer succeeds, so a failed deploy gets retried next time.
#
# A file counts as changed if its size or last-write time differs from the
# manifest entry (or it has no entry yet).
param(
    [Parameter(Mandatory)] [string] $LocalDir,
    [Parameter(Mandatory)] [string] $Manifest,
    [Parameter(Mandatory)] [string] $ListOut
)

$ErrorActionPreference = 'Stop'

# Paths (relative, forward slashes) containing any of these segments are skipped.
$ExcludeDirs = @('__pycache__', '.vscode', '.git')

$root = (Resolve-Path -LiteralPath $LocalDir).Path.TrimEnd('\')

$old = @{}
if (Test-Path -LiteralPath $Manifest) {
    foreach ($line in [IO.File]::ReadAllLines($Manifest)) {
        $parts = $line -split "`t"
        if ($parts.Count -eq 3) { $old[$parts[0]] = "$($parts[1])`t$($parts[2])" }
    }
}

$newManifest = New-Object System.Collections.Generic.List[string]
$changed     = New-Object System.Collections.Generic.List[string]

Get-ChildItem -LiteralPath $root -Recurse -File -Force | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length + 1).Replace('\', '/')
    $segments = $rel -split '/'
    if ($segments | Where-Object { $ExcludeDirs -contains $_ }) { return }
    if ($_.Extension -eq '.pyc') { return }

    $sig = "$($_.Length)`t$($_.LastWriteTimeUtc.Ticks)"
    $newManifest.Add("$rel`t$sig")
    if ($old[$rel] -ne $sig) { $changed.Add($rel) }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines("$Manifest.new", $newManifest, $utf8)
[IO.File]::WriteAllLines($ListOut, $changed, $utf8)

if ($changed.Count -eq 0) {
    Write-Host "No new or changed files."
} else {
    Write-Host "$($changed.Count) new/changed file(s):"
    $changed | ForEach-Object { Write-Host "  $_" }
}
