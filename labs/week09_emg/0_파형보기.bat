@echo off
cd /d "%~dp0"
set /p PORT=<python\port.txt
echo ==========================================================
echo  실시간 파형 (원신호 x - 필터 후 - RMS와 임계 - 상태)
echo  먼저: 스케치 업로드, Arduino 시리얼 모니터 - 플로터 닫기
echo  처음 3초는 힘을 빼고 가만히 (기저선 학습). 창에서 c 키 = 기저선 다시 학습
echo  다 봤으면 그래프 창을 닫는다
echo ==========================================================
python -X utf8 -W ignore python\viz.py live %PORT% emg
if errorlevel 1 pause
