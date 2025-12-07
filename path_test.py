from pathlib import Path

base = Path("/workspace")
malicious_abs = "/etc/passwd"
malicious_rel = "../../etc/passwd"

print(f"Base: {base}")
print(f"Absolute join result: {base / malicious_abs}")
print(f"Relative join result: {base / malicious_rel}")
