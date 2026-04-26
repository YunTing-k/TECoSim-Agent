import time
import requests
from test_config import *

reasoning = False
reasoning_type = "enabled" if reasoning else "disabled"

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
        "model": "deepseek-chat",
        "thinking": {"type": reasoning_type},
    }
    while True:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            if reasoning:
                return (response.json()['choices'][0]['message']['reasoning_content'].strip(),
                        response.json()['choices'][0]['message']['content'].strip())
            else:
                return response.json()['choices'][0]['message']['content'].strip()
        else:
            time.sleep(5)
            continue


if __name__ == "__main__":
    question = "Hello, who are you?"
    if reasoning:
        answer1, answer2 = query(question)
        print(answer1)
        print(answer2)
    else:
        answer = query(question)
        print(answer)
