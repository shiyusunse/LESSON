



if exist %SP_DIR%\scipy\_lib\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\cluster\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\constants\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\datasets\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\fftpack\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\fft\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\integrate\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\interpolate\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\io\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\linalg\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\misc\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\ndimage\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\odr\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\optimize\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\signal\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\sparse\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\spatial\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\special\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\stats\tests exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\_lib\_test_ccallback.cp310-win_amd64.pyd exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\integrate\_test_multivariate.cp310-win_amd64.pyd exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\io\_test_fortran.cp310-win_amd64.pyd exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\ndimage\_ctest.cp310-win_amd64.pyd exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\ndimage\_cytest.cp310-win_amd64.pyd exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %SP_DIR%\scipy\special\_test_internal.cp310-win_amd64.pyd exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
python -c "import scipy; throw_away_the_return_value = scipy.test()" > testlog
IF %ERRORLEVEL% NEQ 0 exit /B 1
python -c "import sys; lines=open('testlog').readlines(); sys.exit(0 if any('conda-forge builds of' in x for x in lines) else 1)"
IF %ERRORLEVEL% NEQ 0 exit /B 1
(pytest --pyargs scipy || if !ERRORLEVEL! neq 0 exit 0) > testlog
IF %ERRORLEVEL% NEQ 0 exit /B 1
python -c "import sys; lines=open('testlog').readlines(); sys.exit(0 if any('conda-forge builds of' in x for x in lines) else 1)"
IF %ERRORLEVEL% NEQ 0 exit /B 1
python -c "import sys; lines=open('testlog').readlines(); sys.exit(0 if any('======== 1 failed' in x for x in lines) else 1)"
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
