@echo off
rem Double-click: backup of the whole Hisaab database into the backups folder (safe while the app is open).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup.ps1"
