
@echo off
title ViralCut AI
cd /d "C:\Users\Ashwin kumar singh\AIRFLOW\viralcut-ai"

echo.
echo ==================================
echo       VIRALCUT AI STARTING
echo ==================================
echo.
echo Please wait while the app starts...
echo Do not close this window while using ViralCut AI.
echo.

"C:\Users\Ashwin kumar singh\AIRFLOW\.venv\Scripts\python.exe" -m streamlit run app/main.py --server.port 8503

echo.
echo ViralCut AI has stopped.
pause
