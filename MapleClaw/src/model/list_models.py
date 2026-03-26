import requests
from pathlib import Path
import yaml

# D:\CODE\MYSELF\SW\MapleClaw\src\config\global_config.yaml
config_path = Path(__file__).resolve().parent.parent / "config" / "global_config.yaml"
with open(file=config_path, mode='r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

# base_url = config.get("model", {}).get("llm_base_url")
# api_key = config.get("model", {}).get("llm_api_key")

# 5.4 模型
base_url = "http://192.168.145.16/v1/"
api_key = "sk-nNjhgftuSH0Bn95V0c2Km6Q3ewlBIu45CTDtJAZSWKMHIgwe"

# sk-nNjhgftuSH0Bn95V0c2Km6Q3ewlBIu45CTDtJAZSWKMHIgwe 4.6
if not base_url:
    print("错误: 未找到 llm_base_url 配置")
    exit(1)

models_url = f"{base_url.rstrip('/')}/models"

headers = {
    "Authorization": f"Bearer {api_key}"
}

try:
    print(f"正在查询可用模型: {models_url}")
    response = requests.get(models_url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        models = data.get("data", [])
        
        print(f"\n找到 {len(models)} 个可用模型:\n")
        print("=" * 80)
        for i, model in enumerate(models, 1):
            model_id = model.get("id", "未知")
            model_type = model.get("type", "")
            owned_by = model.get("owned_by", "")
            
            print(f"{i}. 模型名称: {model_id}")
            if model_type:
                print(f"   类型: {model_type}")
            if owned_by:
                print(f"   提供者: {owned_by}")
            print("-" * 80)
    else:
        print(f"请求失败: HTTP {response.status_code}")
        print(f"响应内容: {response.text}")
        
except requests.exceptions.RequestException as e:
    print(f"请求错误: {e}")
except Exception as e:
    print(f"发生错误: {e}")
