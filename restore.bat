@echo off
rem Double-click: put a backup (.dump) back into the database. Or drag a .dump file onto this file.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore.ps1" "%~1"
