@echo off
title Auto Absen MagangHub - Dashboard
echo ========================================================
echo   Auto Absen MagangHub - Local Dashboard Control Panel
echo ========================================================
echo Membuka browser di http://localhost:8000 ...
echo (Jangan tutup jendela terminal ini selama menggunakan dashboard)
echo.

start http://localhost:8000
"C:\laragon\bin\php\php-7.4.19-Win32-vc15-x64\php.exe" -S localhost:8000
