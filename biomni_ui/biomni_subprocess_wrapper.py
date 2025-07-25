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
    
    print(f"[BIOMNI] Starting analysis for session {session_id}")
    print(f"[BIOMNI] Query: {query}")
    print(f"[BIOMNI] Working directory: {session_outputs_path}")
    
    try:
        # Import Biomni here to avoid import issues if not installed
        try:
            from biomni.agent import A1
            use_mock = False
            print("[BIOMNI] Using real Biomni implementation")
        except ImportError:
            print("[BIOMNI] Biomni not available, using mock implementation")
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
        
        print("[BIOMNI] Agent initialized successfully")
        
        # Execute query
        print("[BIOMNI] Starting query execution...")
        log, final_result = agent.go(query)
        
        print("[BIOMNI] Query execution completed")
        
        # Output log entries
        if log:
            print("[BIOMNI] Processing log entries:")
            for entry in log:
                if entry and entry.strip():
                    print(f"[LOG] {entry}")
        
        # Output final result
        if final_result and final_result.strip():
            print("[BIOMNI] Final result:")
            print(f"[RESULT] {final_result}")
        
        print("[BIOMNI] Analysis completed successfully")
        
    except Exception as e:
        print(f"[ERROR] Execution failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()