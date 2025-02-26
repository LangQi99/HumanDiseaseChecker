from prompt import *
import requests
import json
import traceback
import time
from utils import logger, get_moonshot_response


class Solver:
    def __init__(self, user_input, api_url, headers):
        self.user_input = user_input
        self.url = api_url
        self.headers = headers

    def get_response(self, user_prompt, system_prompt, max_tokens=1024):
        payload = {
            "model": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt
                },
                {
                    "role": "system",
                    "content": system_prompt
                }
            ],
            "stream": False,
            "max_tokens": max_tokens,
            "stop": ["null"],
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": 50,
            "frequency_penalty": 0.5,
            "n": 1,
            "response_format": {"type": "text"}
        }
        response = requests.request("POST",
                                    self.url, json=payload, headers=self.headers)

        response = response.json()['choices'][0]['message']['content']
        logger.info(response)
        return response

    def start(self):
        def generate_stream(self, big_type, all_type, res):
            import concurrent.futures
            result = []
            futures_info = {}
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 批量提交所有任务
                futures = []
                for type in all_type:
                    future = executor.submit(
                        self.get_disease_type_detail, big_type, type)
                    futures.append(future)
                    futures_info[future] = type
                waiting_length = len(futures)

                # 按照任务完成顺序逐个获取结果
                for future in concurrent.futures.as_completed(futures):
                    response = future.result()
                    result.append(response)
                    name = futures_info[future]
                    waiting_length -= 1
                    # 立即流式返回当前结果
                    yield json.dumps({"stream": f"{name}分析完成"}) + "\n"
            res["result"] = result

        def callback(response):
            yield json.dumps({"stream": response}) + "\n"

        def direct_callback(context):
            yield context
        try:
            yield from callback("判断疾病大类中")
            big_type = self.get_disease_type()
            yield from callback(f"初步判断为{big_type} 联网搜索相关疾病中")
            all_type = disease_type[big_type]
            more_type = self.get_more_type()
            all_type.extend(more_type)
            res = {}
            yield from generate_stream(self, big_type, all_type, res)
            small_type_info = str(res["result"])
            # yield from callback(f"初步判断为{small_type_info}")
            final_type = self.get_final_type(small_type_info)
            yield from callback(f"最终判断为{final_type}")
            prob = self.get_prob(final_type)
            yield from callback(f"准确度:{prob}")
            solution, cloud = self.get_solution(final_type)
            yield from callback("分析完成")
            time.sleep(0.2)
            yield from direct_callback(json.dumps({"final_type": final_type, "big_type": big_type,
                                                   "danger": prob, "solution": solution, "cloud": cloud}))
        except Exception as e:
            logger.error(traceback.format_exc())
            yield from direct_callback(json.dumps({"error": "无法判断，请重新输入"}))

    def get_solution(self, final_type):
        system_prompt = "你是一个人类医生，用户会给你几个人类的疾病，以及得病的概率，还有症状，你告诉用户" + \
            "这些疾病的症状，与用户给你的人类疾病症状的符合程度，然后告诉用户，这些疾病成因和治疗方案。不要分条。不要用markdown，平易近人即可" +\
            "最后还要告诉用户，如果需要更准确的疾病分析，还需要什么信息，更多信息的格式（保留【和】符号，要尽可能多，越多越好，但是顺序按重要程度从前到后）：【xx,xxx,xxxx,xxxx】" +\
            "以上回答尽量简短。**要非常简短**"
        result = self.get_response(
            self.user_input + str(final_type), system_prompt, max_tokens=2048).replace("，", ",").replace("、", ",")
        solution = result.split("【")[0]
        prim_cloud = result.split("【")[1].split("】")[0]
        cloud = {}
        words = prim_cloud.split(",")
        third = len(words) // 3
        for i, word in enumerate(words):
            if i < third:
                cloud[word] = 3
            elif i < third * 2:
                cloud[word] = 2
            else:
                cloud[word] = 1

        return solution, cloud

    def get_more_type(self):
        system_prompt = "你是一个人类医生，你根据用户输入的症状，判断人类可能患有的疾病。" + \
            "输出格式是[疾病名称1/疾病名称2/疾病名称3/xxx] 越多越好"
        result = self.get_response(self.user_input, system_prompt)
        return (result.split("[")[1].split("]")[0]).split("/")

    def get_prob(self, final_type):
        system_prompt = "你是一个人类医生，用户会给你几个人类的疾病，以及得病的概率，你给这个牲畜一个准确度（0-100）" + \
            "0是没有可能，100是百分百，注意，如果是10左右，就是我不敢肯定它一定得这个病，因为用户给的描述太少了，症状很广泛。" + \
            "不要轻易给出过高的数值，注意你回复的是一个综合的准确度，而不是每个疾病都要一个准确度。回复时，在最后加上准确度的数值。格式为（保留【和】符号）：【xx】"
        result = self.get_response(str(final_type), system_prompt)
        return result.split("【")[1].split("】")[0]

    def get_disease_type(self):
        system_prompt = "你是一个人类医生，你根据用户输入的症状，判断人类可能患有的疾病大类。" + \
            "以下是九大类，你只能选择这九大类中的一个，回复时，在最后加上大类名称。格式为（保留【和】符号）：【大类名称】  " + \
            disease_type_detail_prompt
        result = self.get_response(
            self.user_input, system_prompt, max_tokens=2048)
        return result.split("【")[1].split("】")[0]

    def get_disease_type_detail(self, big_type, type):
        system_prompt = "你是一个人类医生，你根据用户输入的症状，判断人类可能患有的疾病。" +\
            "我将给你一个疾病列表，无论用户输入什么，你都需要挨个比对判断，先说这个疾病会有什么症状，" +\
            "然后说用户给你的症状跟这个疾病的症状符合程度，得出可能的概率。如果某个疾病十分危险，且用户的描述不是十分肯定，那么这个的概率不能超过10%。注意，你只需要告诉我每个疾病的符合程度" + \
            "，不需要告诉我它最有可能得了什么病。" + \
            "以下是" + big_type + "的疾病列表：" + \
            str(disease_type[big_type])

        # 获取联网信息
        symptoms = ""
        try:
            symptoms = get_moonshot_response(
                self.user_input, f"请搜索 {type} 的百度百科，并告诉我它的症状。")
        except Exception as e:
            logger.error(traceback.format_exc())

        # while True:
        #     try:
        #         symptoms = get_moonshot_response(
        #             self.user_input, f"请搜索 {type} 的百度百科，并告诉我它的症状。")
        #         logger.info(f"{type} 获取联网信息成功")
        #         break
        #     except Exception as e:
        #         if "Error code: 429" in str(e):
        #             logger.info(f"被动 {type} 等待10秒后重试...")
        #             time.sleep(10)
        #         elif "Error code: 428" in str(e):
        #             logger.info(f"手动 {type} 等待10秒后重试...")
        #             time.sleep(10)
        #         else:
        #             logger.error(traceback.format_exc())
        #             break

        if not symptoms:
            symptoms = "联网信息暂时获取失败，没有外置参考资料"
        logger.info(f"{type} 联网信息：{symptoms}")

        command = "**你不需要判断整个疾病列表，我们一个一个来，你现在应该判断的是" + \
            str(type) + "请给出你的分析(症状符合程度，得出可能的概率等,回答尽量简短。**要非常简短**) 参考资料: " + \
            str(symptoms) + " **"
        system_prompt = system_prompt + "\n" + command

        try:
            return self.get_response(self.user_input, system_prompt)
        except Exception as e:
            logger.error(f"{type} 分析失败")
            logger.error(traceback.format_exc())
            return f"{type} 暂时分析失败 不能得出结论 但你不能忽略它"

    def get_final_type(self, small_type_info):
        system_prompt = "你是一个人类医生，你根据用户输入的症状，判断人类可能患有的疾病。" + \
            "用户会给你分析结果，你只能选择这其中的1~3个，如果某个疾病十分危险，且用户的描述不是十分肯定，那么这个的概率不能超过10%，" + \
            "回复时，在最后加上，概率最高的放最前面，最低的放最后面，而且要区分概率，大的拉大，小的拉小，例如有两个，**输出格式为：{\"具体疾病名称1\":\"可能的概率(0-100)\"，\"具体疾病名称2\":\"可能的概率(0-100)\"}  **" + \
            small_type_info
        result = self.get_response(
            small_type_info, system_prompt, max_tokens=2048)
        result = result.replace("，", ",").replace("%", "")
        json_data = "{" + result.split("{")[1].split("}")[0] + "}"
        return json.loads(json_data)
