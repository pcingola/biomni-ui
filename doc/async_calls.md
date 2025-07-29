## Why Async?

- Non-blocking UI: The await calls let the event loop handle other user messages while waiting for I/O (like execute_query).
- Real-time streaming: async for updates the user interface incrementally instead of waiting for the final response.
- Scalability: Multiple sessions can run concurrently without threads or blocking.

## How it works?

### Flowchart

```mermaid
flowchart TD
    A["User sends message"] --> B{"Session & Wrapper exist?"}

    B -- No --> B1["Show error message: 'Session not found'"]
    B -- Yes --> C["Extract & log message"]

    C --> D["Send 'Processing...' placeholder"]
    D --> E["Call stream_response()"]

    subgraph StreamingLoop
        E --> F["Start loop over async output chunks"]
        F --> G{"Chunk is not empty?"}

        G -- No --> F
        G -- Yes --> H["Append chunk to response"]
        H --> I["Count tokens in chunk"]
        I --> J{"Token threshold reached?"}

        J -- No --> F
        J -- Yes --> K["Update message in UI"]
        K --> F

        F --> L["Final message update (if needed)"]
        L --> M["Log 'Query completed'"]
    end

    M --> Z["Done"]
````