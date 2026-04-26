# After build: refresh Desktop shortcut. Pure client: one onedir under dist\.
$ErrorActionPreference = "Continue"
try {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $distRoot = Join-Path $projectRoot "dist"
    if (-not (Test-Path -LiteralPath $distRoot)) {
        Write-Host "[skip] dist folder not found"
        exit 0
    }
    $exe = $null
    foreach ($d in @(Get-ChildItem -LiteralPath $distRoot -Directory -ErrorAction SilentlyContinue)) {
        $candidate = Join-Path $d.FullName ($d.Name + ".exe")
        if (Test-Path -LiteralPath $candidate) { $exe = $candidate; break }
    }
    if (-not $exe) {
        Write-Host "[skip] No exe found under dist\ (build first)"
        exit 0
    }

    $desktop = [Environment]::GetFolderPath("Desktop")
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        Write-Host "[skip] Desktop folder not found"
        exit 0
    }

    $appDirName = Split-Path -LiteralPath $exe -Leaf
    $appDirName = [System.IO.Path]::GetFileNameWithoutExtension($appDirName)
    $lnkPath = Join-Path $desktop ($appDirName + ".lnk")
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = Split-Path -LiteralPath $exe -Parent
    $shortcut.IconLocation = "$exe,0"
    $shortcut.Description = "Warehouse dispatch client"
    $shortcut.Save()

    Write-Host "[ok] Desktop shortcut updated: $lnkPath"
    Write-Host "[tip] If the icon still looks old: restart Explorer or sign out once (Windows icon cache)."
}
catch {
    Write-Host "[warn] Desktop shortcut not updated: $($_.Exception.Message)"
}
exit 0
