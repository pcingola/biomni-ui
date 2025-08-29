import json
import re
from pydantic import BaseModel, Field, field_validator, ConfigDict

class Resource(BaseModel):
    """
    Object representing a resource with its name and reason for selection.
    
    Attributes:
    - name: Name of the resource.
    - reason: Reason for selecting this resource.
    """
    name: str = Field(..., description="Name of the resource")
    reason: str | None = Field(..., description="Reason for selecting this resource")
    
    def __str__(self) -> str:
        return f"{self.name}: {self.reason or 'no reason provided'}"
    
class SelectedToolsModel(BaseModel):
    """
    Object representing the selected tools, data lake files and software libraries for a query.
    
    Attributes:
    - tools: List of selected tools with their names and reasons for selection.
    - data_lake: List of selected data lake items with their names and descriptions.
    - libraries: List of selected software libraries with their names and descriptions.
    """
    tools: list[Resource]
    data_lake: list[Resource]
    libraries: list[Resource]
    
    def __str__(self) -> str:                
        report = "Selected Tools:\n"
        for tool in self.tools:
            report += f"- {tool.name}: {tool.reason}\n"
        
        report += "\nSelected Data Lake Items:\n"
        for item in self.data_lake:
            report += f"- {item.name}: {item.reason}\n"
        
        report += "\nSelected Libraries:\n"
        for lib in self.libraries:
            report += f"- {lib.name}: {lib.reason}\n"
        
        return report
    
class Step(BaseModel):
    
    model_config = ConfigDict(extra='ignore')
    name: str
    description: str
    resources: list[Resource] | None = None
    result: str | None = None
    cites: list[str] | None = None
    output_files: list[str] | None = None
    stderr: str | None = None

class ExecutionResult(BaseModel):
    """
    Object representing the response for a query execution.

    Attributes:
    - step: The current step being executed.
    - summary: A summary of the execution process.
    - jupyter_notebook: Jupyter notebook content if applicable.
    """
    model_config = ConfigDict(extra='ignore')
    step: list[Step] = Field(default_factory=list)
    summary: str = Field("", description="Summary of the execution process")
    jupyter_notebook: str | None = Field(
        None, description="Jupyter notebook content if applicable"
    )
    
    @field_validator("step", mode="before")
    def _coerce_step(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            return [v]
        if isinstance(v, str):
            s = v.strip()

            # 1) strip code fences / language hints
            if s.startswith("```"):
                s = s.strip("`")
                s = s.split("\n", 1)[1] if "\n" in s else s

            # 2) keep only the JSON-ish slice (between first '[' and last ']')
            i, j = s.find("["), s.rfind("]")
            if i != -1 and j != -1 and i < j:
                s = s[i:j+1]

            # 3) normalize quotes and remove trailing commas
            s = s.replace("“", '"').replace("”", '"').replace("’", "'")
            s = re.sub(r",\s*([}\]])", r"\1", s)

            # 4) try to parse array; if object, wrap as list
            try:
                parsed = json.loads(s)
                if isinstance(parsed, dict):
                    return [parsed]
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass

            # last resort: try to parse the whole original string
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return [parsed]
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                # be lenient: empty list instead of raising (prevents hard crash)
                return []
        return v