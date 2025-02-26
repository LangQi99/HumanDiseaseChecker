import os
is_proxy = True
moonshot_api_key = "sk-xxx"
siliconflow_api_key = "sk-xxx"
if is_proxy:
    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:10802'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:10802'
