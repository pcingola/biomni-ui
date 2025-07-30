#!/usr/bin/env python3
"""
Subprocess wrapper for Biomni agent to enable real-time stdout/stderr streaming.
This script is called as a subprocess to run the Biomni agent.
"""
import sys
import os
import json
from pathlib import Path

from Biomni.biomni.agent.a1 import A1
from Biomni.biomni.utils import pretty_print
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
    
    # Set working directory to session outputs path
    session_outputs_path = Path(config['session_outputs_path'])
    # Ensure the directory exists before changing to it
    session_outputs_path.mkdir(parents=True, exist_ok=True)
    os.chdir(str(session_outputs_path))
    
    print(f"[BIOMNI] Starting analysis for session {session_id}", flush=True)
    print(f"[BIOMNI] Query: {query}", flush=True)
    print(f"[BIOMNI] Working directory: {session_outputs_path}", flush=True)
    
    try:
        # Import Biomni
        from biomni.agent import A1
        print("[BIOMNI] Using Biomni implementation", flush=True)
        
        # Initialize agent
        biomni_data_path = config['biomni_data_path']
        
        # Debug: Print configuration values
        print(f"[DEBUG] LLM Model: {config['biomni_llm_model']}", flush=True)
        print(f"[DEBUG] Base URL: {config.get('biomni_base_url')}", flush=True)
        print(f"[DEBUG] API Key: {config.get('biomni_api_key', 'EMPTY')[:20]}...", flush=True)
        
        # Set OpenAI API key environment variable for custom models
        api_key = config.get('biomni_api_key', 'EMPTY')
        if api_key and api_key != 'EMPTY':
            os.environ['OPENAI_API_KEY'] = api_key
            print("[DEBUG] Set OPENAI_API_KEY environment variable", flush=True)
        
        agent = A1(
            path=biomni_data_path,
            llm=config['biomni_llm_model'],
            timeout_seconds=config['biomni_timeout_seconds'],
            base_url=config.get('biomni_base_url'),
            api_key=api_key
        )
        
        print("[BIOMNI] Agent initialized successfully", flush=True)
        
        # Execute query with real-time streaming
        print("[BIOMNI] Starting query execution...", flush=True)
        
        try:
            # Set up the agent for streaming
            from langchain_core.messages import HumanMessage
            inputs = {"messages": [HumanMessage(content=query)], "next_step": None}
            config = {"recursion_limit": 500, "configurable": {"thread_id": 42}}
            
            # Stream the execution and output in real-time
            step_count = 0
            final_message = None
            
            for step_output in agent.app.stream(inputs, stream_mode="values", config=config):
                step_count += 1
                message = step_output["messages"][-1]
                final_message = message
                
                # Import pretty_print from biomni.utils for consistent formatting
                from biomni.utils import pretty_print
                formatted_output = pretty_print(message)
                
                if formatted_output and formatted_output.strip():
                    print(f"[LOG] Step {step_count}: {formatted_output}", flush=True)
            
            # Get the final result
            if final_message and hasattr(final_message, 'content'):
                final_result = final_message.content
                if final_result and final_result.strip():
                    print(f"[RESULT] {final_result}", flush=True)
            
            print("[BIOMNI] Analysis completed successfully", flush=True)
            
        except Exception as streaming_error:
            print(f"[BIOMNI] Streaming failed, falling back to standard execution: {streaming_error}", flush=True)
            
            # Fallback to the original synchronous method
            log, final_result = agent.go(query)
            
            print("[BIOMNI] Query execution completed", flush=True)
            
            # Output log entries
            if log:
                print("[BIOMNI] Processing log entries:", flush=True)
                for entry in log:
                    if entry and entry.strip():
                        print(f"[LOG] {entry}", flush=True)
            
            # Output final result
            if final_result and final_result.strip():
                print("[BIOMNI] Final result:", flush=True)
                print(f"[RESULT] {final_result}", flush=True)
            
            print("[BIOMNI] Analysis completed successfully", flush=True)
        
    except Exception as e:
        print(f"[ERROR] Execution failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()