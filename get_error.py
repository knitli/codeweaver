import subprocess
out = subprocess.run(["uv", "run", "pytest", "tests/integration/real/test_full_pipeline.py::test_indexing_performance_with_real_providers"], capture_output=True, text=True)
print("\n".join([line for line in out.stdout.split("\n") if "Exception" in line or "Error" in line or "Traceback" in line][-10:]))
