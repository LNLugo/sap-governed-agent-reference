"""Step 2: the thin slice. One question, one tool, one grounded answer, one trace.

Run: python thin_slice.py "Who is business partner 17100001 and where are they located?"
(replace the ID with one you picked in Step 0)
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from gen_ai_hub.orchestration_v2.models.config import ModuleConfig, OrchestrationConfig
from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails
from gen_ai_hub.orchestration_v2.models.message import (
    ChatMessage, SystemMessage, ToolChatMessage, UserMessage)
from gen_ai_hub.orchestration_v2.models.template import PromptTemplatingModuleConfig, Template
from gen_ai_hub.orchestration_v2.models.tools import function_tool
from gen_ai_hub.orchestration_v2.service import OrchestrationService

from sap_tools import fetch_business_partner

load_dotenv()

SYSTEM = (
    "You answer questions about SAP business partners using ONLY the results of your tools. "
    "Always cite the business partner ID you used. If the tools do not return the answer, "
    "say you cannot answer from SAP data. Never invent values."
)


@function_tool()
def get_business_partner(business_partner_id: str) -> str:
    """Look up an SAP business partner by ID. Returns name, category and addresses."""
    return fetch_business_partner(business_partner_id).model_dump_json()


TOOLS = {"get_business_partner": get_business_partner}


def trace(record: dict):
    Path("traces").mkdir(exist_ok=True)
    with open("traces/traces.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def ask(question: str, max_turns: int = 4) -> str:
    request_id, started = str(uuid.uuid4()), time.time()
    steps = []
    template = Template(
        template=[SystemMessage(content=SYSTEM), UserMessage(content="{{?question}}")],
        tools=list(TOOLS.values()),
    )
    llm = LLMModelDetails(name=os.getenv("MODEL_NAME", "gpt-4o"))
    config = OrchestrationConfig(modules=ModuleConfig(
        prompt_templating=PromptTemplatingModuleConfig(prompt=template, model=llm)))
    service = OrchestrationService(config=config)
    values = {"question": question}

    response = service.run(placeholder_values=values)
    history: List[ChatMessage] = []
    answer = None
    for _ in range(max_turns):
        message = response.final_result.choices[0].message
        if not message.tool_calls:
            answer = message.content
            break
        if not history:
            history.extend(response.intermediate_results.templating)
        history.append(message)
        for call in message.tool_calls:
            name, args = call.function.name, call.function.parse_arguments()
            if name not in TOOLS:
                result = json.dumps({"error": f"unknown tool {name}"})
            else:
                try:
                    result = TOOLS[name].execute(**args)
                except Exception as e:  # surface tool failures to the model and the trace
                    result = json.dumps({"error": str(e)})
            steps.append({"tool": name, "args": args, "result_chars": len(str(result))})
            history.append(ToolChatMessage(content=str(result), tool_call_id=call.id))
        response = service.run(placeholder_values=values, history=history)
    else:
        answer = "Stopped: too many tool calls without an answer."

    trace({"request_id": request_id, "question": question, "steps": steps,
           "answer": answer, "latency_s": round(time.time() - started, 2)})
    return answer


if __name__ == "__main__":
    print(ask(" ".join(sys.argv[1:]) or "Who is business partner 17100001?"))
