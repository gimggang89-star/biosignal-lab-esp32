@echo off
cd /d "%~dp0"
set MPLBACKEND=Agg
if not exist results mkdir results
echo ==========================================================
echo  00. 설치 확인 (보드 필요 없음, 1분) - 합성 예시로 파이썬 도구가 도는지 본다
echo ==========================================================
python -c "import numpy, scipy, matplotlib, serial; serial.Serial; print('패키지 OK')"
if errorlevel 1 goto pkg
python -X utf8 -W ignore python\viz.py record samples\synthetic_3_contractions.bin emg 18 results\_설치확인.csv
if errorlevel 1 goto fail
python -X utf8 -W ignore python\emg_analyze.py detect results\_설치확인.csv --labels labels\e4_labels.csv
if errorlevel 1 goto fail
echo.
echo 위에 표가 나오고 "펌웨어 (k=5/3)" 줄의 전환이 6 이면 준비 끝 (합성 신호라 숫자는 실제와 다르다)
pause
exit /b
:pkg
echo.
echo [실패] 패키지가 없거나 serial 이 잘못 깔려 있다. 아래 두 줄을 cmd 에 실행한 뒤 다시:
echo   python -m pip uninstall -y serial
echo   python -m pip install numpy scipy matplotlib pyserial
pause
exit /b
:fail
echo.
echo [실패] 위 오류 메시지를 확인하세요
pause
