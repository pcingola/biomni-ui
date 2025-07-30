#!/usr/bin/env python3
"""
Subprocess wrapper for Biomni agent to enable real-time stdout/stderr streaming.
This script is called as a subprocess to run the Biomni agent.
"""
import sys
import os
import json
from pathlib import Path

from biomni.agent import A1
from biomni.utils import pretty_print
from langchain_core.messages import HumanMessage


def stream_agent_execution(agent, query):
    """Stream agent execution output in real-time."""
    agent.critic_count = 0
    agent.user_task = query

    if agent.use_tool_retriever:
        # Handle tool retrieval (same as original go() method)
        import glob
        
        # Gather all available resources
        all_tools = agent.tool_registry.tools if hasattr(agent, "tool_registry") else []

        # Data lake items with descriptions
        data_lake_path = agent.path + "/data_lake"
        data_lake_content = glob.glob(data_lake_path + "/*")
        data_lake_items = [x.split("/")[-1] for x in data_lake_content]

        # Create data lake descriptions for retrieval
        data_lake_descriptions = []
        for item in data_lake_items:
            description = agent.data_lake_dict.get(item, f"Data lake item: {item}")
            data_lake_descriptions.append({"name": item, "description": description})

        # Add custom data items to retrieval if they exist
        if hasattr(agent, "_custom_data") and agent._custom_data:
            for name, info in agent._custom_data.items():
                data_lake_descriptions.append({"name": name, "description": info["description"]})

        # Libraries with descriptions
        library_descriptions = []
        for lib_name, lib_desc in agent.library_content_dict.items():
            library_descriptions.append({"name": lib_name, "description": lib_desc})

        # Add custom software items to retrieval if they exist
        if hasattr(agent, "_custom_software") and agent._custom_software:
            for name, info in agent._custom_software.items():
                if not any(lib["name"] == name for lib in library_descriptions):
                    library_descriptions.append({"name": name, "description": info["description"]})

        # Use retrieval to get relevant resources
        resources = {
            "tools": all_tools,
            "data_lake": data_lake_descriptions,
            "libraries": library_descriptions,
        }

        # Use prompt-based retrieval with the agent's LLM
        selected_resources = agent.retriever.prompt_based_retrieval(query, resources, llm=agent.llm)
        print("[BIOMNI] Using prompt-based retrieval with the agent's LLM", flush=True)

        # Extract the names from the selected resources for the system prompt
        selected_resources_names = {
            "tools": selected_resources["tools"],
            "data_lake": [],
            "libraries": [lib["name"] if isinstance(lib, dict) else lib for lib in selected_resources["libraries"]],
        }

        # Process data lake items to extract just the names
        for item in selected_resources["data_lake"]:
            if isinstance(item, dict):
                selected_resources_names["data_lake"].append(item["name"])
            elif isinstance(item, str) and ": " in item:
                name = item.split(": ")[0]
                selected_resources_names["data_lake"].append(name)
            else:
                selected_resources_names["data_lake"].append(item)

        # Update the system prompt with the selected resources
        agent.update_system_prompt_with_selected_resources(selected_resources_names)

    inputs = {"messages": [HumanMessage(content=query)], "next_step": None}
    config = {"recursion_limit": 500, "configurable": {"thread_id": 42}}
    agent.log = []

    # Stream the workflow execution and print output in real-time
    for s in agent.app.stream(inputs, stream_mode="values", config=config):
        message = s["messages"][-1]
        out = pretty_print(message)
        agent.log.append(out)
        
        # Print the output immediately for real-time streaming
        print(out, flush=True)


def main():
    if len(sys.argv) != 4:
        print("Usage: biomni_subprocess_wrapper.py <session_id> <query> <config_json>", file=sys.stderr)
        sys.exit(1)
    
    session_id = sys.argv[1]
    query = sys.argv[2]
    config_json = sys.argv[3]
    
    # Parse config
    config = json.loads(config_json)
    
    # The subprocess is already started with the correct working directory (cwd parameter in biomni_wrapper.py)
    # so we don't need to change directory again. Just ensure the directory exists.
    session_outputs_path = Path(config['session_outputs_path'])
    session_outputs_path.mkdir(parents=True, exist_ok=True)
    
    # Verify we're in the correct directory (should already be set by subprocess cwd parameter)
    current_cwd = Path.cwd()
    print(f"[BIOMNI] Current working directory: {current_cwd}", flush=True)
    
    print(f"[BIOMNI] Starting analysis for session {session_id}", flush=True)
    print(f"[BIOMNI] Query: {query}", flush=True)
    print(f"[BIOMNI] Working directory: {session_outputs_path}", flush=True)
    
    try:
        print("[BIOMNI] Initializing Biomni agent...", flush=True)

        agent = A1(
            path=config['biomni_data_path'],
            llm=config['biomni_llm_model'],
            timeout_seconds=config['biomni_timeout_seconds'],
            base_url=config.get('biomni_base_url'),
            api_key=config['biomni_api_key']
        )
        
        print("[BIOMNI] Agent initialized successfully", flush=True)
        
        # Execute query with real-time streaming
        print("[BIOMNI] Starting query execution...", flush=True)

        # Stream the agent execution by intercepting the workflow stream
        stream_agent_execution(agent, query)
        
        print("[BIOMNI] Analysis completed successfully", flush=True)
                
    except Exception as e:
        print(f"[ERROR] Execution failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()