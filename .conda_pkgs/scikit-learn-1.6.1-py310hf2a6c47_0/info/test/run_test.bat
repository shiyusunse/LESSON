



pytest --pyargs sklearn -k "not (_not_a_real_test or test_loadings_converges)" -nauto --timeout=1200 --durations=50
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
