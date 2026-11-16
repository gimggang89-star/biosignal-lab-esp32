@echo off
cd /d "%~dp0"
set /p PORT=<python\port.txt
set MPLBACKEND=Agg
if not exist results mkdir results
echo ==========================================================
echo  실험 5. 근피로 - 30~50 퍼센트 힘으로 60초 유지 (아프면 바로 멈춤) (66초)
echo  먼저: 실험 4 스케치 그대로
echo        Arduino 시리얼 모니터 - 플로터는 닫기
echo  화면에 뜨는 대로 따라 한다 (1초 전에 미리 알려 준다). 처음 3초는 힘 빼기
echo  준비되면 아무 키
echo ==========================================================
pause > nul
python -X utf8 -W ignore python\viz.py record %PORT% emg 66 results\e5.csv --cue labels\e5_labels.csv
if errorlevel 1 goto fail
echo.
python -X utf8 -W ignore python\emg_analyze.py fatigue results\e5.csv --labels labels\e5_labels.csv
python -X utf8 -W ignore python\emg_analyze.py spec results\e5.csv --labels labels\e5_labels.csv
start "" "results"
echo.
echo 끝. 숫자는 results\e5_*.txt, 그림은 results\e5_*.png
pause
exit /b
:fail
echo.
echo [실패] 위 메시지를 확인: 시리얼 모니터 - 플로터를 닫았는지, python\port.txt 의 포트(%PORT%), 스케치 업로드
pause
