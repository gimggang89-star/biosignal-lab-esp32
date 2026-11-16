@echo off
cd /d "%~dp0"
set /p PORT=<python\port.txt
set MPLBACKEND=Agg
if not exist results mkdir results
echo ==========================================================
echo  실험 1. 원신호 관찰 - 이완과 수축 번갈아 (20초)
echo  먼저: arduino\student\emg_chain 업로드 (빈칸 그대로)
echo        Arduino 시리얼 모니터 - 플로터는 닫기
echo  화면에 뜨는 대로 따라 한다 (1초 전에 미리 알려 준다). 처음 3초는 힘 빼기
echo  준비되면 아무 키
echo ==========================================================
pause > nul
python -X utf8 -W ignore python\viz.py record %PORT% emg 20 results\e1.csv --cue labels\e1_labels.csv
if errorlevel 1 goto fail
echo.
python -X utf8 -W ignore python\emg_analyze.py time results\e1.csv --auto
start "" "results"
echo.
echo 끝. 숫자는 results\e1_*.txt, 그림은 results\e1_*.png
pause
exit /b
:fail
echo.
echo [실패] 위 메시지를 확인: 시리얼 모니터 - 플로터를 닫았는지, python\port.txt 의 포트(%PORT%), 스케치 업로드
pause
