@echo off
setlocal
set "ZONE04_GAME_DIR=%~dp0"
if not exist "%ZONE04_GAME_DIR%Zone04.exe" (
    echo Extract the entire ZIP before creating the shortcut.
    pause
    exit /b 1
)
powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; $dir = $env:ZONE04_GAME_DIR; $desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory); $shell = New-Object -ComObject WScript.Shell; $link = $shell.CreateShortcut((Join-Path $desktop 'Zone 04.lnk')); $link.TargetPath = Join-Path $dir 'Zone04.exe'; $link.WorkingDirectory = $dir; $link.IconLocation = $link.TargetPath + ',0'; $link.Save()"
if errorlevel 1 (
    echo Could not create the desktop shortcut.
    pause
    exit /b 1
)
echo Desktop shortcut created: Zone 04
if /i not "%~1"=="--quiet" pause
