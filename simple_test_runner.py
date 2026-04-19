
import sys
import os
import tempfile
import traceback
from pathlib import Path

import io

# Mock pytest
class MockCapsys:
    def __init__(self):
        self.out_io = io.StringIO()
        self.err_io = io.StringIO()
        self.old_stdout = None
        self.old_stderr = None

    def __enter__(self):
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = self.out_io
        sys.stderr = self.err_io
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

    def readouterr(self):
        class Output:
            def __init__(self, out, err):
                self.out = out
                self.err = err
        return Output(self.out_io.getvalue(), self.err_io.getvalue())

class MockPytest:
    def raises(self, exc):
        class Context:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(f"Did not raise {exc}")
                return issubclass(exc_type, exc)
        return Context()

sys.modules['pytest'] = MockPytest()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import tests.test_mai as test_mai

def run_tests():
    test_funcs = [name for name in dir(test_mai) if name.startswith("test_")]
    passed = 0
    failed = 0
    
    print(f"Running {len(test_funcs)} tests...")
    
    for name in test_funcs:
        func = getattr(test_mai, name)
        try:
            if "capsys" in func.__code__.co_varnames:
                capsys = MockCapsys()
                with capsys:
                    func(capsys)
            else:
                func()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}")
            traceback.print_exc()
            failed += 1
            
    print(f"\nSummary: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
