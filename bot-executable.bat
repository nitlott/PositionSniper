 @echo off
cd c:\modular_strategybot
python start.py
timeout /t 7 /nobreak > NUL
bot-executable.bat