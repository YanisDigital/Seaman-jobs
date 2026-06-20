@echo off
REM Сборка автономного SeamanJobs.exe (one-folder, с упакованным Chromium).
REM Требует один раз: .venv с зависимостями + `python -m playwright install chromium`.
cd /d "%~dp0"
echo === Устанавливаю зависимости десктопа ===
".venv\Scripts\python.exe" -m pip install -r requirements-desktop.txt
echo === Проверяю браузер для maritime-zone ===
".venv\Scripts\python.exe" -m playwright install chromium
echo === Собираю .exe (это займёт несколько минут) ===
".venv\Scripts\python.exe" -m PyInstaller --noconfirm "seaman_jobs.spec"
echo.
echo Готово. Приложение: dist\SeamanJobs\SeamanJobs.exe
echo Раздавайте папку dist\SeamanJobs целиком (можно заархивировать в zip).
pause
