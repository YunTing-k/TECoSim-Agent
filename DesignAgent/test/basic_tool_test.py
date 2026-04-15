from openai import OpenAI
from test_config import *

client = OpenAI(
    api_key=KEY,
    base_url=URL,
)
"""tool definition"""
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市名称，例如：北京、上海",
                    }
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        }
    }
]


def get_weather(city: str) -> str:
    weather_data = {
        "北京": "晴天，25°C，湿度 40%",
        "上海": "多云，28°C，湿度 65%",
        "广州": "雷阵雨，30°C，湿度 80%",
    }
    return weather_data.get(city, f"未找到 {city} 的天气信息，请尝试其他城市。")


messages = [{"role": "system", "content": "You are a helpful assistant with access to weather tools."}]

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
            tools=tools,
            temperature=0.7,
        )
    except Exception as e:
        print(f"API error: {e}")
        continue

    assistant_message = response.choices[0].message
    assistant_content = assistant_message.content or ""
    tool_calls = assistant_message.tool_calls

    if tool_calls:
        messages.append(assistant_message.model_dump())

        for tool_call in tool_calls:
            func_name = tool_call.function.name
            arguments = eval(tool_call.function.arguments)
            if func_name == "get_weather":
                location = arguments.get("location")
                weather_result = get_weather(location)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": weather_result,
                })
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"未知工具: {func_name}",
                })

        try:
            second_response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=tools,
                temperature=0.7,
            )
            final_assistant = second_response.choices[0].message.content or ""
            print(f"Agent: {final_assistant}\n")
            messages.append({"role": "assistant", "content": final_assistant})
        except Exception as e:
            print(f"API error on second call: {e}")
            continue
    else:
        print(f"Agent: {assistant_content}\n")
        messages.append({"role": "assistant", "content": assistant_content})
