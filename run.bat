@echo off
setlocal
cd /d "%~dp0backend"

if exist ".venv\Scripts\python.exe" goto use_venv

rem Try python directly first
where python >nul 2>nul
if not errorlevel 1 (
  python -c "import uvicorn" >nul 2>nul
  if not errorlevel 1 (
    python -m uvicorn app.main:app --reload
    goto done
  )
)

rem Try py launcher with Python 3.11 then general 3
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 -c "import uvicorn" >nul 2>nul
  if not errorlevel 1 (
    py -3.11 -m uvicorn app.main:app --reload
    goto done
  )
  py -3 -c "import uvicorn" >nul 2>nul
  if not errorlevel 1 (
    py -3 -m uvicorn app.main:app --reload
    goto done
  )
)

echo Python or required packages were not found.
echo Set up a virtual environment and install the dependencies:
echo   cd backend
echo   py -3.11 -m venv .venv
echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
pause
exit /b 1

:use_venv
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload
if errorlevel 1 (
  echo Could not start InquireX. From backend, run: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

:done
exit /b 0
