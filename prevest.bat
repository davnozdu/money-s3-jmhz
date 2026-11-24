@echo off
rem Pretahnete PDF tisk JMHZ z Money S3 na tento soubor.
chcp 65001 >nul
where py >nul 2>nul
if %errorlevel%==0 (py -3 "%~dp0jmhz.py" %*) else (python "%~dp0jmhz.py" %*)
pause
