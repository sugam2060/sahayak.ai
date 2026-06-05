import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from shared.config import NVIDIA_API_KEY

url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {NVIDIA_API_KEY}",
    "Content-Type": "application/json"
}
data = {
    "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
}

try:
    print("Sending request to integrate.api.nvidia.com...")
    response = requests.post(url, headers=headers, json=data, timeout=10)
    print("Status code:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("Error:", e)
