@echo off
rem Drag and drop .prproj files (or folders) onto this file to convert them for Windows (NFC).
rem Double-click without files to open the GUI.
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set SCRIPT=%~dp0prp_path_fixer.py
where py > nul 2>&1 && (set PY=py -3) || (set PY=python)
if "%~1"=="" (
  %PY% "%SCRIPT%"
) else (
  %PY% "%SCRIPT%" --to win -v %*
  pause
)
