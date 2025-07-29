## Initial prompt

```text
I want to build a minimal Chainlit UI to interface with Biomni (included as a submodule in this project), with the following constraints:

- The model should run asynchronously to avoid blocking the UI. Use built-in async capabilities, and stream outputs live from Biomni to the UI.
- Support basic session handling and logging: save conversation history and execution results in isolated directories using simple session IDs.
- Only expose the main A1 agent functionality.
- No authentication needed for now.
- Configuration (e.g. model, API key, data paths) should be handled via .env files. Do not validate variables used only by Biomni, Biomni handles its own requirements.
- Separate the Biomni data path from the directory used for logs and intermediate results. The latter should live outside the project directory.
- Avoid adding unnecessary features. Focus strictly on the core functionality for this first iteration.
- Keep the UI minimal and professional, no emojis or extra visuals.


For the async execution do something like:

import asyncio
import chainlit as cl

@cl.on_message
async def on_message(msg: cl.Message):
    await cl.Message(content="Starting async dual-stream command...").send()
    
    # Create async subprocess
    process = await asyncio.create_subprocess_shell(
        "for i in {1..5}; do echo stdout $i; echo stderr $i 1>&2; sleep 1; done",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Async function to read from a stream
    async def read_stream(stream, stream_name):
        if stream:
            while True:
                line = await stream.readline()
                if not line:  # EOF
                    break
                # Decode bytes to string and strip whitespace
                text = line.decode('utf-8').strip()
                await cl.Message(content=f"[{stream_name}] {text}").send()
    
    # Run both stream readers and process completion concurrently
    stdout_task = asyncio.create_task(read_stream(process.stdout, "STDOUT"))
    stderr_task = asyncio.create_task(read_stream(process.stderr, "STDERR"))
    
    # Wait for all tasks to complete
    await asyncio.gather(stdout_task, stderr_task, process.wait())
    
    await cl.Message(content=f"Process finished with exit code {process.returncode}").send()
```

```text
This code is supposed to, when the user submits a message, run a call to the agent in async mode. While the process is going on we need to display realtime logs on UI capturing stdout and stderr. Is this code archiving this?
```

```text
is there any code here that could be cleaned up? Remove all code that is not being used, its overcomplicated or it's not part of a core feature for the MVP
```

```text
I want to reimplement how we parse the output of the model: 

Rules:
- Remove everything that is not needed. No need for splicing.
- The parser must be simple and robust.
- Maintain line breaks and formatting to maximize readability.
- The parsed blocks should appear in the same order as in the original message.

Restrictions:
- The messages coming from the model come always after the
`================================== Ai Message ==================================` flag. 
  - Dont show anything before this flag.
  - Split the messages accordingly.
  - Code should be provided as code blocks. Solutions and observations should be cleary flagged. 
```