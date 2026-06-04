from openai import OpenAI
from test_config import *  # a test_config.py is need to store you URL and API key

client = OpenAI(
    api_key=KEY,
    base_url=URL,
)

messages = [{"role": "system", "content": "You are a helpful assistant."}]

print("Agent start, text 'exit' to exit\n")

while True:
    user_input = input("You: ").strip()
    if user_input.lower() in ("exit", "quit"):
        break
    if not user_input:
        continue

    messages.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
        )
    except Exception as e:
        print(f"API error: {e}")
        continue

    assistant_response = response.choices[0].message.content
    print(f"Agent: {assistant_response}\n")

    messages.append({"role": "assistant", "content": assistant_response})
