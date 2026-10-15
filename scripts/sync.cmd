@echo off
cd /d C:\Users\itzik\Desktop\CLAUDE\score-oracle
set PYTHONIOENCODING=utf-8
echo ==== %date% %time% >> output\sync.log
"C:\Users\itzik\AppData\Local\Programs\Python\Python312\python.exe" -m oracle sync >> output\sync.log 2>&1
