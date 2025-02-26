import wikipedia
import wikipediaapi
from openai import OpenAI
from openai.types.chat.chat_completion import Choice
import json
from typing import *
import time
import random
import os
from config import moonshot_api_key, is_proxy
wikipedia.set_lang("zh")
wiki_wiki = wikipediaapi.Wikipedia(
    language='zh',
    user_agent='anonymous@anonymous.com'
)


class logger:
    @staticmethod
    def info(message):
        print(f"\033[92m[INFO] {message}\033[0m")

    @staticmethod
    def error(message):
        print(f"\033[91m[ERROR] {message}\033[0m")


client = OpenAI(
    base_url="https://api.moonshot.cn/v1",
    api_key=moonshot_api_key,
)


# search 工具的具体实现，这里我们只需要返回参数即可
def search_impl(arguments: Dict[str, Any]) -> Any:
    """
    在使用 Moonshot AI 提供的 search 工具的场合，只需要原封不动返回 arguments 即可，
    不需要额外的处理逻辑。

    但如果你想使用其他模型，并保留联网搜索的功能，那你只需要修改这里的实现（例如调用搜索
    和获取网页内容等），函数签名不变，依然是 work 的。

    这最大程度保证了兼容性，允许你在不同的模型间切换，并且不需要对代码有破坏性的修改。
    """
    return arguments


def chat(messages) -> Choice:
    completion = client.chat.completions.create(
        model="moonshot-v1-128k",
        messages=messages,
        temperature=0.3,
        tools=[
            {
                # <-- 使用 builtin_function 声明 $web_search 函数，请在每次请求都完整地带上 tools 声明
                "type": "builtin_function",
                "function": {
                    "name": "$web_search",
                },
            }
        ]
    )
    return completion.choices[0]


def get_moonshot_response(system_prompt, user_prompt):
    # 使用类变量来跟踪调用次数和时间
    # import time
    # if not hasattr(get_moonshot_response, 'last_call_time'):
    #     get_moonshot_response.last_call_time = time.time()
    #     get_moonshot_response.call_count = 1
    # else:
    #     current_time = time.time()
    #     if current_time - get_moonshot_response.last_call_time <= 1:
    #         get_moonshot_response.call_count += 1
    #         if get_moonshot_response.call_count > 1:
    #             raise Exception("Error code: 428")
    #     else:
    #         get_moonshot_response.last_call_time = current_time
    #         get_moonshot_response.call_count = 1
    # time.sleep(random.random()*5)
    # return "这里原本是网络上的参考资料，但为了省钱，测试阶段，你只能看到这段话"
    messages = [
        {"role": "system", "content": system_prompt},
    ]

    # 初始提问
    messages.append({
        "role": "user",
        "content": user_prompt
    })

    finish_reason = None
    while finish_reason is None or finish_reason == "tool_calls":
        choice = chat(messages)
        finish_reason = choice.finish_reason
        if finish_reason == "tool_calls":  # <-- 判断当前返回内容是否包含 tool_calls
            # <-- 我们将 Kimi 大模型返回给我们的 assistant 消息也添加到上下文中，以便于下次请求时 Kimi 大模型能理解我们的诉求
            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:  # <-- tool_calls 可能是多个，因此我们使用循环逐个执行
                tool_call_name = tool_call.function.name
                # <-- arguments 是序列化后的 JSON Object，我们需要使用 json.loads 反序列化一下
                tool_call_arguments = json.loads(tool_call.function.arguments)
                if tool_call_name == "$web_search":
                    tool_result = search_impl(tool_call_arguments)
                else:
                    tool_result = f"Error: unable to find tool by name '{tool_call_name}'"

                # 使用函数执行结果构造一个 role=tool 的 message，以此来向模型展示工具调用的结果；
                # 注意，我们需要在 message 中提供 tool_call_id 和 name 字段，以便 Kimi 大模型
                # 能正确匹配到对应的 tool_call。
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call_name,
                    # <-- 我们约定使用字符串格式向 Kimi 大模型提交工具调用结果，因此在这里使用 json.dumps 将执行结果序列化成字符串
                    "content": json.dumps(tool_result),
                })

    return choice.message.content  # <-- 在这里，我们才将模型生成的回复返回给用户


# def http_get_info(name, keyword='症状'):
#     # https://baike.baidu.com/search?word=%E9%B8%A1%E7%BE%BD%E8%99%B1%E7%97%85&rn=1&enc=utf8&onlySite=1&fromModule=lemma_search-box
#     return

    # def http_get_info(name, keyword='症状'):
    #     page = wiki_wiki.page(name)
    #     if not page.exists():
    #         page_title = wikipedia.search(name)[0]  # 取第一个结果
    #         logger.info(f"{name} 最接近的页面标题: {page_title}")
    #         page = wiki_wiki.page(page_title)
    #     else:
    #         logger.info(f"{name} 页面存在")
    #     if page.exists():
    #         sections = page.sections
    #         for section in sections:
    #             if keyword in section.title:
    #                 return section.text
    #     return "页面不存在，没有外置参考资料"


def format_html(http_info):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(http_info, 'lxml')
    formatted_html = soup.prettify()
    return formatted_html


# def extract_symptoms(http_info):
#     """查找症状相关的文本"""
#     symptoms = []
#     lines = http_info.split('\n')
#     is_symptom_section = False
#     if "本词条是一个多义词，请在下列义项中选择浏览" in http_info:
#         return -1

#     for line in lines:
#         if '症状' in line and '<a name=' in line:
#             is_symptom_section = True
#             continue
#         # if '<a name="' in line and is_symptom_section:
#         #     break
#         if is_symptom_section:
#             print(line)
#             # import time
#             # time.sleep(0.01)
#             if '<span class="text_ki2nn" data-text="true">' in line:
#                 text = line
#                 # 去除所有HTML标签
#                 while '<' in text and '>' in text:
#                     start = text.find('<')
#                     end = text.find('>', start) + 1
#                     text = text[:start] + text[end:]
#                 if text.strip():
#                     symptoms.append(text.strip())
#     return ''.join(symptoms)
