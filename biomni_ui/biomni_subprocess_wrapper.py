#!/usr/bin/env python3
"""
Subprocess wrapper for Biomni agent to enable real-time stdout/stderr streaming.
This script is called as a subprocess to run the Biomni agent.
"""
import sys
import os
import json
from pathlib import Path

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
    os.chdir(str(session_outputs_path))
    
    print(f"[BIOMNI] Starting analysis for session {session_id}", flush=True)
    print(f"[BIOMNI] Query: {query}", flush=True)
    print(f"[BIOMNI] Working directory: {session_outputs_path}", flush=True)
    
    try:
        # Import Biomni here to avoid import issues if not installed
        try:
            from biomni.agent import A1
            use_mock = False
            print("[BIOMNI] Using real Biomni implementation", flush=True)
        except ImportError:
            print("[BIOMNI] Biomni not available, using mock implementation", flush=True)
            # Add the parent directory to path to import mock
            sys.path.append(str(Path(__file__).parent))
            from mock_biomni import MockA1 as A1
            use_mock = True
        
        # Initialize agent
        biomni_data_path = config['biomni_data_path']
        
        if use_mock:
            agent = A1(
                path=biomni_data_path,
                llm=config['biomni_llm_model']
            )
        else:
            agent = A1(
                path=biomni_data_path,
                llm=config['biomni_llm_model'],
                timeout_seconds=config['biomni_timeout_seconds'],
                base_url=config.get('biomni_base_url'),
                api_key=config.get('biomni_api_key', 'EMPTY')
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