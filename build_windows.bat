@echo off
REM Builds "Presenter View.exe" on a Windows PC. Needs Python 3.10+ installed.
python -m venv .venv-win
call .venv-win\Scripts\activate
pip install Pillow pymupdf==1.26.5 pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "Presenter View" --icon icon.ico presenter_notes.py
echo.
echo Done: dist\Presenter View.exe
pause
