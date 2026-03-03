



f2py -h
IF %ERRORLEVEL% NEQ 0 exit /B 1
python -c "import numpy, sys; sys.exit(not numpy.test(verbose=1, label='full', tests=None, extra_argv=['-k', 'not (_not_a_real_test)', '-nauto', '--timeout=3000', '--durations=50', '--maxfail=100']))"
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
