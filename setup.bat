@echo off
REM Crea el entorno virtual (.venv), instala las librerias y genera __pycache__\main.cpython-311.pyc
REM Requiere Python 3.11 instalado (comando "py").

py -3.11 -m venv .venv
if errorlevel 1 (
    echo No se pudo crear el entorno virtual. Verifique que Python 3.11 este instalado.
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m py_compile main.py

echo.
echo Listo. Para ejecutar la API:
echo     .venv\Scripts\activate
echo     uvicorn main:app --reload
echo Documentacion interactiva: http://127.0.0.1:8000/docs
