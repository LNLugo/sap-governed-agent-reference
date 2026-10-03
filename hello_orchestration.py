"""Step 1: prove you can call a model through SAP's Orchestration Service V2.

Run: python hello_orchestration.py
"""
import os

from dotenv import load_dotenv
from gen_ai_hub.orchestration_v2.models.config import ModuleConfig, OrchestrationConfig
from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails
from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage
from gen_ai_hub.orchestration_v2.models.template import PromptTemplatingModuleConfig, Template
from gen_ai_hub.orchestration_v2.service import OrchestrationService

load_dotenv()

template = Template(template=[
    SystemMessage(content="You are a concise SAP architecture assistant."),
    UserMessage(content="{{?question}}"),
])
llm = LLMModelDetails(name=os.getenv("MODEL_NAME", "gpt-4o"), params={"max_completion_tokens": 200})
config = OrchestrationConfig(modules=ModuleConfig(
    prompt_templating=PromptTemplatingModuleConfig(prompt=template, model=llm)))

result = OrchestrationService(config=config).run(
    placeholder_values={"question": "In two sentences, what is clean core in SAP S/4HANA?"})
print(result.final_result.choices[0].message.content)
