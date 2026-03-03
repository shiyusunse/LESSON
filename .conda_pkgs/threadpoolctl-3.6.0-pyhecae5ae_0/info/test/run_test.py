#  tests for threadpoolctl-3.6.0-pyhecae5ae_0 (this is a generated file);
print('===== testing package: threadpoolctl-3.6.0-pyhecae5ae_0 =====');
print('running run_test.py');
#  --- run_test.py (begin) ---
import numpy
from threadpoolctl import threadpool_info, threadpool_limits


if __name__ == "main":
    print(threadpool_info())

    with threadpool_limits(1):
        print(threadpool_info())
#  --- run_test.py (end) ---

print('===== threadpoolctl-3.6.0-pyhecae5ae_0 OK =====');
print("import: 'threadpoolctl'")
import threadpoolctl

