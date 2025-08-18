import json
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
    stdout: str | None = None
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
    
    # Accept dict, list, or JSON string for 'step'
    @field_validator("step", mode="before")
    def _parse_step_if_string(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                v = json.loads(v)  # was a JSON-encoded string
            except Exception:
                raise ValueError("`step` must be an array or JSON array string.")
        if isinstance(v, dict):
            return [v]  # accept a single object
        return v