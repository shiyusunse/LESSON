import importlib.util
import json
import sys

module_path = sys.argv[1]
entry_point = sys.argv[2]
spec = importlib.util.spec_from_file_location('candidate_module', module_path)
if spec is None or spec.loader is None:
    raise RuntimeError('failed to load candidate module')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
func = getattr(module, entry_point)
payload = json.loads(sys.stdin.read())
if isinstance(payload, list):
    func(*payload)
else:
    func(payload)
