import json
from ..shared.llm import chat as llm_chat
from ..shared.eln_tools import IndigoELNClient

# Define function schemas for Ollama native tool calling
ELN_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "List all projects in the Indigo-ELN book.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_notebooks",
            "description": "List all notebooks available in the Indigo-ELN book.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_experiments",
            "description": "List all experiments in a specific notebook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "The ID of the project"},
                    "notebook_id": {"type": "string", "description": "The ID of the notebook"}
                },
                "required": ["project_id", "notebook_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_experiment",
            "description": "Create a new experiment in the ELN book.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "The ID of the project"},
                    "notebook_id": {"type": "string", "description": "The ID of the notebook"},
                    "experiment_name": {"type": "string", "description": "Name of the new experiment"}
                },
                "required": ["project_id", "notebook_id", "experiment_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_experiment",
            "description": "Retrieve detailed information of a specific experiment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "notebook_id": {"type": "string"},
                    "experiment_id": {"type": "string"}
                },
                "required": ["project_id", "notebook_id", "experiment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_experiment_comments",
            "description": "Update or set the comments/notes/description of a specific experiment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "notebook_id": {"type": "string"},
                    "experiment_id": {"type": "string"},
                    "comments": {"type": "string", "description": "New comments or log text to update"}
                },
                "required": ["project_id", "notebook_id", "experiment_id", "comments"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are the Griffin ELN Controller Agent.
Your job is to manage the user's Electronic Lab Notebook (Indigo-ELN) based on their natural language instructions.
You have access to tools/functions to search, list, create, and update projects, notebooks, and experiments.

If the user asks you to perform an action, you must use one of the tools.
To trigger a tool call, respond in ONE of two ways:
1. Native Tool Call (if supported by your model engine).
2. JSON Fallback: Respond with a JSON block in the format:
   ACTION: {"tool": "tool_name", "arg1": "val1", ...}

Available Tools:
- list_projects()
- list_notebooks()
- list_experiments(project_id, notebook_id)
- create_experiment(project_id, notebook_id, experiment_name)
- get_experiment(project_id, notebook_id, experiment_id)
- update_experiment_comments(project_id, notebook_id, experiment_id, comments)

Always explain what action you are taking first, followed by the tool call or the ACTION JSON block.
"""

def execute_eln_agent(
    prompt: str,
    server_url: str,
    username: str,
    password: str,
    model_name: str = "llama3.1:8b"
) -> str:
    """Executes the ELN Controller Agent loop with tool calling and fallbacks."""
    # 1. Authenticate with Indigo-ELN
    client = IndigoELNClient(base_url=server_url)
    if not client.login(username, password):
        return "Error: Failed to authenticate with Indigo-ELN. Please check your credentials and make sure the server is running."

    # 2. Call the LLM with system prompt and tool definitions
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = llm_chat(
            model=model_name,
            messages=messages,
            task="chat",
            options={"temperature": 0.1},
            tools=ELN_FUNCTIONS
        )
    except Exception as e:
        return f"Error communicating with local LLM: {str(e)}"

    content = response.get("message", {}).get("content", "")
    tool_calls = response.get("message", {}).get("tool_calls", [])

    # 3. Parse action (either via native tool calls or ACTION JSON block)
    action_to_take = None
    args = {}

    if tool_calls:
        # Native tool call detected
        tool_call = tool_calls[0]
        action_to_take = tool_call.get("function", {}).get("name")
        action_args = tool_call.get("function", {}).get("arguments", {})
        # Sometimes arguments are returned as JSON string
        if isinstance(action_args, str):
            try:
                args = json.loads(action_args)
            except Exception:
                args = {}
        else:
            args = action_args
    elif "ACTION:" in content:
        # Fallback JSON parsing
        try:
            action_part = content.split("ACTION:")[1].strip()
            # Clean up potential markdown formatting around JSON
            if "```json" in action_part:
                action_part = action_part.split("```json")[1].split("```")[0].strip()
            elif "```" in action_part:
                action_part = action_part.split("```")[1].strip()
            
            action_data = json.loads(action_part)
            action_to_take = action_data.get("tool")
            args = {k: v for k, v in action_data.items() if k != "tool"}
        except Exception as e:
            return f"The LLM tried to take an action but the JSON format was invalid: {content}"

    if not action_to_take:
        # No action selected, just return LLM's text response
        return content

    # 4. Execute the chosen tool
    result_str = ""
    try:
        if action_to_take == "list_projects":
            res = client.list_projects()
            result_str = f"Found projects:\n" + json.dumps(res, indent=2)
        elif action_to_take == "list_notebooks":
            res = client.list_notebooks()
            result_str = f"Found notebooks:\n" + json.dumps(res, indent=2)
        elif action_to_take == "list_experiments":
            res = client.list_experiments(args.get("project_id"), args.get("notebook_id"))
            result_str = f"Experiments summary:\n" + json.dumps(res, indent=2)
        elif action_to_take == "create_experiment":
            res = client.create_experiment(
                args.get("project_id"),
                args.get("notebook_id"),
                args.get("experiment_name")
            )
            result_str = f"Experiment created:\n" + json.dumps(res, indent=2)
        elif action_to_take == "get_experiment":
            res = client.get_experiment(
                args.get("project_id"),
                args.get("notebook_id"),
                args.get("experiment_id")
            )
            result_str = f"Experiment details:\n" + json.dumps(res, indent=2)
        elif action_to_take == "update_experiment_comments":
            res = client.update_experiment_comments(
                args.get("project_id"),
                args.get("notebook_id"),
                args.get("experiment_id"),
                args.get("comments")
            )
            result_str = f"Update status:\n" + json.dumps(res, indent=2)
        else:
            return f"Unknown tool choice: {action_to_take}"
    except Exception as e:
        return f"Error executing tool '{action_to_take}': {str(e)}"

    # 5. Send result back to LLM to summarize
    final_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": f"Taking action: {action_to_take} with args {args}"},
        {"role": "user", "content": f"Tool Execution Result:\n{result_str}\n\nPlease summarize this result and explain it to the user."}
    ]

    try:
        final_resp = llm_chat(
            model=model_name,
            messages=final_messages,
            task="chat",
            options={"temperature": 0.5}
        )
        return final_resp.get("message", {}).get("content", f"Action '{action_to_take}' complete. Result: {result_str}")
    except Exception:
        return f"Action '{action_to_take}' executed successfully. Here is the raw result:\n{result_str}"
