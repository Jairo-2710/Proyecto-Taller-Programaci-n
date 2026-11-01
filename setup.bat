@echo off
REM Crea el entorno virtual (.venv), instala las librerias y genera __pycache__\main.cpython-3XX.pyc
REM Recomendado: Python 3.11. Si no esta instalado, usa el Python que encuentre.

set PY=
py -3.11 --version >nul 2>&1 && set PY=py -3.11
if not defined PY (
    py -3 --version >nul 2>&1 && set PY=py -3
)
if not defined PY (
    python --version >nul 2>&1 && set PY=python
)
if not defined PY (
    echo No se encontro Python. Instale Python 3.11 desde https://www.python.org/downloads/
    echo y marque "Add python.exe to PATH" y "py launcher" durante la instalacion.
    exit /b 1
)

echo Usando: %PY%
%PY% --version

%PY% -m venv .venv
if errorlevel 1 (
    echo No se pudo crear el entorno virtual.
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Fallo la instalacion de librerias. Se recomienda Python 3.11.
    exit /b 1
)
python -m py_compile main.py

echo.
echo Listo. Para ejecutar la API:
echo     .venv\Scripts\activate
echo     uvicorn main:app --reload
echo Documentacion interactiva: http://127.0.0.1:8000/docs
