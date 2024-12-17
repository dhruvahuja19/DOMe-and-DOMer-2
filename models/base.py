from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pathlib import Path

@dataclass
class WebInteraction:
    """Represents a web interaction instruction."""
    action: str  # click, type, hover
    selector_type: str  # css, xpath, id
    selector_value: str
    input_text: Optional[str] = None
    description: Optional[str] = None

@dataclass
class TaskResult:
    """Represents the result of executing a task."""
    task_id: str
    success: bool
    before_screenshot: Optional[str] = None
    after_screenshot: Optional[str] = None
    html_element: Optional[str] = None
    accessibility_tree: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "before_screenshot": self.before_screenshot,
            "after_screenshot": self.after_screenshot,
            "html_element": self.html_element,
            "accessibility_tree": self.accessibility_tree,
            "error": self.error,
            "metadata": self.metadata
        }

class BaseModel(ABC):
    """Base class for all models that can run the DOM benchmark."""
    
    def __init__(self, model_name: str, model_config: Dict[str, Any]):
        self.model_name = model_name
        self.model_config = model_config
        
    @abstractmethod
    def parse_task(self, task: Dict[str, Any]) -> WebInteraction:
        """Parse a task definition into a web interaction instruction.
        
        Args:
            task: Task definition from dom_tasks.jsonl
            
        Returns:
            WebInteraction object with parsed instructions
        """
        pass
    
    @abstractmethod
    def handle_error(self, task: Dict[str, Any], error: str) -> WebInteraction:
        """Handle errors during task execution and optionally retry.
        
        Args:
            task: Original task definition
            error: Error message from failed execution
            
        Returns:
            New WebInteraction to try, or None to give up
        """
        pass
    
    @abstractmethod
    def validate_result(self, task: Dict[str, Any], result: TaskResult) -> bool:
        """Validate if the task execution was successful.
        
        Args:
            task: Original task definition
            result: Result from task execution
            
        Returns:
            True if task was successful, False otherwise
        """
        pass

    def run_task(self, task: Dict[str, Any], executor) -> TaskResult:
        """Run a single task using the model's logic.
        
        Args:
            task: Task definition from dom_tasks.jsonl
            executor: TaskExecutor instance to run web interactions
            
        Returns:
            TaskResult with execution results
        """
        try:
            # Parse task into web interaction
            interaction = self.parse_task(task)
            
            # Execute the interaction
            result = executor.execute_interaction(interaction)
            
            # Validate the result
            success = self.validate_result(task, result)
            result.success = success
            
            return result
            
        except Exception as e:
            # Try to handle the error
            try_again = self.handle_error(task, str(e))
            if try_again:
                return self.run_task(task, executor)
            
            # If can't handle, return failure
            return TaskResult(
                task_id=task["id"],
                success=False,
                error=str(e)
            )
