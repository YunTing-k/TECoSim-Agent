import time
import requests
from test_config import *


def query(messages):
    url = URL + "chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % KEY
    }
    messages = [{"role": "user", "content": f"{messages}"}]
    print("message:", messages)
    data = {
        "messages": messages,
        "stream": False,
        "do_sample": True,
        "repetition_penalty": 1.00,
        "temperature": 1e-5,
        "top_k": 20,
        "model": "deepseek-chat"
    }
    while True:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            time.sleep(5)
            continue


if __name__ == "__main__":
    question = "Hello, who are you?"
    answer = query(question)
    print(answer)
