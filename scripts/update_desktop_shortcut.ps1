# After build: refresh Desktop shortcut so icon is read from the new exe (IconLocation = exe,0).
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $projectRoot "dist\仓库物资调度\仓库物资调度.exe"

if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host "[skip] Build output not found: $exe"
    exit 0
}

$desktop = [Environment]::GetFolderPath("Desktop")
if ([string]::IsNullOrWhiteSpace($desktop)) {
    Write-Host "[skip] Desktop folder not found"
    exit 0
}

$lnkPath = Join-Path $desktop "仓库物资调度.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = Split-Path -LiteralPath $exe -Parent
$shortcut.IconLocation = "$exe,0"
$shortcut.Description = "Warehouse dispatch app"
$shortcut.Save()

Write-Host "[ok] Desktop shortcut updated: $lnkPath"
Write-Host "[tip] If the icon still looks old: restart Explorer from Task Manager, or sign out once (Windows icon cache)."
