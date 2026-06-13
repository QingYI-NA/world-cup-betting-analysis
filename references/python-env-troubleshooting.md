# Windows PYTHONHOME Conflict

## Symptom
Python crashes with "SRE module mismatch" on import, even with correct executable.

## Root Cause
`PYTHONHOME` env var points to broken uv Python 3.11 path:
`C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none`

This forces all Python versions to load stdlib from there.

## Fix
Delete `PYTHONHOME` and `UV_INTERNAL__PYTHONHOME` from Windows system env vars.

## Workaround (built into main.py)
main.py auto-clears uv PYTHONHOME at startup:
```python
if "uv" in os.environ.get("PYTHONHOME", ""):
    os.environ.pop("PYTHONHOME", None)
```
