@echo off
rem Double-click: start Hisaab Portal WITHOUT demo data (existing data is kept; an empty database stays empty).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" -NoDemo
