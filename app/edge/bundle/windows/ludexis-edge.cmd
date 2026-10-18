@echo off
rem Runs the Ludexis edge command; see "ludexis-edge help".
powershell -NoProfile -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\Ludexis\edge\ludexis-edge.ps1" %*
