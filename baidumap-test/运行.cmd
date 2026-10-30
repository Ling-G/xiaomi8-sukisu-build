@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"
set "MAP_PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%MAP_PYTHON%" goto run
set "MAP_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%MAP_PYTHON%" goto run
set "MAP_PYTHON=python"
:run
"%MAP_PYTHON%" -X utf8 baidumap_flow.py %*
set "MAP_EXIT=%ERRORLEVEL%"
echo.
echo Exit code: %MAP_EXIT%
pause
popd
exit /b %MAP_EXIT%
