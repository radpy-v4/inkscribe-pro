@echo off
chcp 65001 >nul
setlocal

set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=v1.0.0"

echo ==========================================================
echo    InkScribe Pro - Otomatik Release Paketi Hazırlayıcı   
echo    Hedef Sürüm: %VERSION%
echo ==========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release.ps1" -Version "%VERSION%"

echo.
pause
