import subprocess, sys, time, urllib.request, urllib.parse, json

print("Starting uvicorn server...")
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd="C:/Users/Victor/Documents/Hackathon"
)
time.sleep(6)
print("Server should be up now.\n")

# 1) Health check
print("=== HEALTH CHECK ===")
try:
    resp = urllib.request.urlopen("http://localhost:8000/health", timeout=5)
    print(resp.read().decode())
except Exception as e:
    print(f"Error: {e}")

# 2) SMS webhook test
print("\n=== SMS WEBHOOK TEST ===")
try:
    data = urllib.parse.urlencode({
        "From": "+18777804236",
        "Body": "Hello",
        "MessageSid": "TEST_002"
    }).encode()
    req = urllib.request.Request("http://localhost:8000/webhook", data=data, method="POST")
    resp = urllib.request.urlopen(req, timeout=10)
    print(resp.read().decode())
except Exception as e:
    print(f"Error: {e}")

# 3) Wait then check students
print("\nWaiting 5 seconds...")
time.sleep(5)

print("\n=== STUDENTS LIST ===")
try:
    req = urllib.request.Request("http://localhost:8000/api/students")
    req.add_header("X-Instructor-Id", "1")
    resp = urllib.request.urlopen(req, timeout=5)
    raw = resp.read().decode()
    try:
        parsed = json.loads(raw)
        print(json.dumps(parsed, indent=2))
    except:
        print(raw)
except Exception as e:
    print(f"Error: {e}")

# Cleanup
print("\n=== SERVER STDERR (tail) ===")
proc.terminate()
try:
    _, stderr = proc.communicate(timeout=5)
    lines = stderr.decode().strip().split("\n")
    for line in lines[-20:]:
        print(line)
except:
    proc.kill()
    print("(force killed)")

print("\nDone.")
