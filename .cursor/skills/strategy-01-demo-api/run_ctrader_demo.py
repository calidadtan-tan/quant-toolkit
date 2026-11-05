import os, sys, subprocess
from pathlib import Path

env_path = Path(os.environ.get(
    "CTRADER_DEMO_ENV",
    r"C:\Users\calidad\AppData\Local\Temp\ctrader-demo-secure\ctrader-openapi-46950-demo.env",
))
if not env_path.is_file():
    print(f'{{"code":1,"ok":false,"error":"missing_env","path":"{env_path}"}}')
    sys.exit(1)
for line in env_path.read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    os.environ[k.strip()] = v.strip()

client = Path(os.environ.get(
    "CTRADER_DEMO_CLIENT",
    r"C:\Users\calidad\Projects\quant-toolkit\projects\ctrader-demo-client",
))
os.chdir(client)
py = os.environ.get(
    "CTRADER_DEMO_PYTHON",
    r"C:\Users\calidad\AppData\Local\Programs\Python\Python312-arm64\python.exe",
)
r = subprocess.run([py, "-m", "ctrader_demo", *sys.argv[1:]])
sys.exit(r.returncode)
