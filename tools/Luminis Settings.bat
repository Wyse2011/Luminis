@echo off
rem Opens the Luminis Settings window (export / import Luminis settings between materials).
python "%~dp0luminis_settings.py"
if errorlevel 1 pause
