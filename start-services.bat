@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "SOA_ROOT=%~dp0"
set "SOA_DRY_RUN="
if not "%~2"=="" goto usage
if /i "%~1"=="--dry-run" set "SOA_DRY_RUN=1"
if /i "%~1"=="--help" goto help
if not "%~1"=="" if not defined SOA_DRY_RUN goto usage

rem Check every prerequisite before starting any process.
for %%S in (auth-service academic-services regist-service topic-service) do (
    if not exist "%SOA_ROOT%services\%%S\venv\Scripts\python.exe" (
        echo ERROR: Missing "%SOA_ROOT%services\%%S\venv\Scripts\python.exe"
        echo Prepare each service's venv and requirements as described in README.md.
        goto missing
    )
    if not exist "%SOA_ROOT%services\%%S\manage.py" (
        echo ERROR: Missing "%SOA_ROOT%services\%%S\manage.py"
        goto missing
    )
)
if not exist "%SOA_ROOT%fe\package.json" (
    echo ERROR: Missing "%SOA_ROOT%fe\package.json"
    exit /b 1
)
if not exist "%SOA_ROOT%fe\node_modules\.bin\vite.cmd" (
    echo ERROR: Missing frontend dependencies. Run npm ci in the fe directory first.
    exit /b 1
)
"%SystemRoot%\System32\where.exe" node.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not available on PATH.
    exit /b 1
)
"%SystemRoot%\System32\where.exe" npm.cmd >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm.cmd is not available on PATH.
    exit /b 1
)

if defined SOA_DRY_RUN echo DRY RUN: No services will be started.
call :backend auth-service 8001
call :backend academic-services 8002
call :backend regist-service 8003
call :backend topic-service 8004
echo [frontend :5173] cd /d "%SOA_ROOT%fe" ^&^& npm.cmd run dev
if not defined SOA_DRY_RUN start "SOA frontend :5173" /D "%SOA_ROOT%fe" "%ComSpec%" /d /k "npm.cmd run dev"
echo.
echo Frontend: http://localhost:5173
echo Consul and API Gateway must be started separately.
if not defined SOA_DRY_RUN echo Launch requested. Check each window for readiness/errors. Stop with Ctrl+C in each window.
exit /b 0

:backend
echo [%~1 :%~2] cd /d "%SOA_ROOT%services\%~1" ^&^& "%SOA_ROOT%services\%~1\venv\Scripts\python.exe" "%SOA_ROOT%services\%~1\manage.py" runserver 0.0.0.0:%~2
if not defined SOA_DRY_RUN start "SOA %~1 :%~2" /D "%SOA_ROOT%services\%~1" "%ComSpec%" /d /k ""%SOA_ROOT%services\%~1\venv\Scripts\python.exe" "%SOA_ROOT%services\%~1\manage.py" runserver 0.0.0.0:%~2"
exit /b 0

:usage
echo ERROR: Unsupported arguments.
echo Usage: start-services.bat [--dry-run ^| --help]
exit /b 2

:missing
exit /b 1

:help
echo Usage: start-services.bat [--dry-run ^| --help]
echo Starts four Django backends and the Vite frontend in separate console windows.
echo Prepare service venvs, frontend dependencies, .env and database first.
echo --dry-run checks prerequisites and prints commands without starting services.
echo Consul and API Gateway are not started by this script.
exit /b 0
