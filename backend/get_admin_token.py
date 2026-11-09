
import json
import getpass
import urllib.request
import urllib.error

username = "lewy"
password = getpass.getpass("Administrator password: ")

payload = json.dumps({
    "username": username,
    "password": password,
}).encode("utf-8")

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/token/",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("Login successful.")
        print("ACCESS TOKEN (keep private):")
        print(result["access"])
except urllib.error.HTTPError as error:
    print("Login failed:", error.read().decode("utf-8"))
