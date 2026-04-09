from openai import OpenAI
from test_config import *

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
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            stream=True,
        )
    except Exception as e:
        print(f"API error: {e}")
        continue

    full_response = ""
    print("Agent: ", end="", flush=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)
            full_response += content
    print("\n")
    messages.append({"role": "assistant", "content": full_response})
