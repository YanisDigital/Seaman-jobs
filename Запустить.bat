@echo off
REM Запуск графического интерфейса из исходников (для разработки/проверки).
REM Конечному пользователю давайте собранный dist\SeamanJobs\SeamanJobs.exe.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "gui.py"
