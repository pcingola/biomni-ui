import json
from pydantic import BaseModel, Field, model_validator, ConfigDict

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
    
    def __str__(self) -> str:
        out = f"● {self.name}\n{self.description}\n"
        if self.result:
            out += f"Result: {self.result}\n"
        if self.stderr:
            out += f"Error : {self.stderr}\n"
        return out
    
    @model_validator(mode='before')
    @classmethod
    def _coerce_step(cls, v):
        if isinstance(v, str):
            try: v = json.loads(v)
            except Exception: return {"name": "Unknown step", "description": v}
        if isinstance(v, dict) and isinstance(v.get("resources"), str):
            try: v["resources"] = json.loads(v["resources"])
            except Exception: pass
        return v

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
    
    @model_validator(mode='before')
    @classmethod
    def _coerce_exec(cls, v):
        if isinstance(v, dict):
            data = dict(v)
            if "step" not in data and "steps" in data:
                data["step"] = data.pop("steps")
            s = data.get("step")
            if isinstance(s, str):
                try: data["step"] = json.loads(s)
                except Exception: data["step"] = [s]
            if isinstance(data.get("step"), list):
                fixed = []
                for item in data["step"]:
                    if isinstance(item, str):
                        try: fixed.append(json.loads(item))
                        except Exception: fixed.append(item)
                    else:
                        fixed.append(item)
                data["step"] = fixed
            data.setdefault("summary", "")
            return data
        if isinstance(v, str):
            try: return json.loads(v)
            except Exception: return {"step": [], "summary": v}
        return v