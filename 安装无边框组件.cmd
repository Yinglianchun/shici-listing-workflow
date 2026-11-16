@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "C:\Python313\python.exe" goto fixedpython
set "WORKBENCH_PYTHON="
for %%V in (314 313 312 311 310) do if not defined WORKBENCH_PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "WORKBENCH_PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
if defined WORKBENCH_PYTHON goto userpython
where py >nul 2>nul
if errorlevel 1 goto missingpython
py -3 -m pip install PySide6
pause
exit /b
:fixedpython
"C:\Python313\python.exe" -m pip install PySide6
pause
exit /b
:userpython
"%WORKBENCH_PYTHON%" -m pip install PySide6
pause
exit /b
:missingpython
echo Please install Python 3.10 or newer, then start again.
pause
exit /b 1
