@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "C:\Python313\pythonw.exe" goto fixedpython
set "WORKBENCH_PYTHON="
for %%V in (314 313 312 311 310) do if not defined WORKBENCH_PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe" set "WORKBENCH_PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe"
if defined WORKBENCH_PYTHON goto userpython
where pyw >nul 2>nul
if errorlevel 1 goto missingpython
start "" pyw -3 "%~dp0launcher.py"
exit /b
:fixedpython
start "" "C:\Python313\pythonw.exe" "%~dp0launcher.py"
exit /b
:userpython
start "" "%WORKBENCH_PYTHON%" "%~dp0launcher.py"
exit /b
:missingpython
echo Please install Python 3.10 or newer, then start again.
pause
exit /b 1
