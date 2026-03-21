from langchain.chat_models import init_chat_model
from pathlib import Path
import yaml


global_config_path = Path(__file__).resolve().parent.parent / "config" / "global_config.yaml"
with open(file=global_config_path, mode='r', encoding='utf-8') as file:
    config = yaml.safe_load(file)
model_config = config.get("model")


def get_llm():
    llm = init_chat_model(
        model=model_config.get("llm_name","gpt-5.2"),
        model_provider=model_config.get("llm_provider"),
        base_url = model_config.get("llm_base_url"),
        api_key =   model_config.get("llm_api_key"),
    )
    return llm


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage
    llm = get_llm()
    # ans = llm.invoke({"user":"你好，你是谁"})，
    query = HumanMessage(content="你好，你是谁")  # 或者直接进行询问
    ans = llm.invoke([query])
    print(ans.content if hasattr(ans, "content") else ans)
