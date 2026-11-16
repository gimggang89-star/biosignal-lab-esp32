@echo off
cd /d "%~dp0"
set /p PORT=<python\port.txt
set MPLBACKEND=Agg
if not exist results mkdir results
echo ==========================================================
echo  실험 3. 노력 단계 10-25-50-75-100 퍼센트를 3초씩 (30초)
echo  먼저: 실험 2 스케치 그대로 (업로드 필요 없음)
echo        Arduino 시리얼 모니터 - 플로터는 닫기
echo  화면에 뜨는 대로 따라 한다 (1초 전에 미리 알려 준다). 처음 3초는 힘 빼기
echo  준비되면 아무 키
echo ==========================================================
pause > nul
python -X utf8 -W ignore python\viz.py record %PORT% emg 30 results\e3.csv --cue labels\e3_labels.csv
if errorlevel 1 goto fail
echo.
python -X utf8 -W ignore python\emg_analyze.py force results\e3.csv --labels labels\e3_labels.csv
start "" "results"
echo.
echo 끝. 숫자는 results\e3_*.txt, 그림은 results\e3_*.png
pause
exit /b
:fail
echo.
echo [실패] 위 메시지를 확인: 시리얼 모니터 - 플로터를 닫았는지, python\port.txt 의 포트(%PORT%), 스케치 업로드
pause
