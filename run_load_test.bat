@echo off
echo ========================================
echo EduTwin Load Test Runner
echo ========================================
echo.

REM Check if locust is installed
python -c "import locust" 2>nul
if %errorlevel% neq 0 (
    echo Installing locust...
    pip install locust
)

echo.
echo Starting load test...
echo Host: https://edutwin.online
echo Duration: 5 minutes
echo Users: 20 concurrent (ramp up over 1 min)
echo.

REM Run test with CSV output
locust -f load_test.py ^
  --host=https://edutwin.online ^
  --users 20 ^
  --spawn-rate 2 ^
  --run-time 5m ^
  --headless ^
  --csv=load_test_results ^
  --html=load_test_report.html

echo.
echo ========================================
echo Test completed!
echo Results saved to: load_test_results_*.csv
echo HTML Report: load_test_report.html
echo ========================================
pause
