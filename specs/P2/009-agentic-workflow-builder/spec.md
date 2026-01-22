# Feature Spec: Agentic Workflow Builder

**Feature ID**: 009-agentic-workflow-builder  
**Priority**: P2 (Medium)  
**Status**: Planning  
**Created**: January 17, 2026

## Problem Statement

Currently, the Godfather can interact with DeniDin through:
- Simple chat messages
- Scheduled proactive chats (Feature 008)
- MCP tool invocations (Features 004, 005)
- Basic commands

However, there's no way to create **complex, multi-step workflows** that combine these capabilities into intelligent automation sequences. The Godfather cannot:

- Chain multiple actions together ("When X happens, do Y, then Z")
- Create conditional logic ("If A, then B, else C")
- Build reusable workflow templates
- Leverage AI to make intelligent decisions within workflows
- Create sophisticated business processes without coding

**Vision**: Enable the Godfather to create powerful, AI-driven workflows using natural language - similar to how Spec Kit works for coding, but for general-purpose automation.

## Use Cases

### Business Process Automation

**1. Client Onboarding Workflow**
```
When: New client added to system
Then:
  1. Send WhatsApp welcome message with company intro
  2. Create client folder in memory with initial context
  3. Schedule weekly check-in for next 4 weeks
  4. Create first invoice template
  5. Add to CRM (future integration)
  6. Send me summary of setup
```

**2. Invoice Follow-up Workflow**
```
When: Invoice created
Then:
  1. Wait 7 days
  2. If invoice status == "unpaid":
     - Send polite payment reminder to client
     - Log reminder in memory
     - Wait 7 more days
  3. If still unpaid after 14 days:
     - Notify me via WhatsApp
     - Ask if I want to send final notice
     - If I approve: send final notice
  4. If still unpaid after 30 days:
     - Mark as seriously overdue
     - Schedule urgent review with me
```

**3. Weekly Report Workflow**
```
Every: Friday at 4pm
Do:
  1. Query memory for this week's activities:
     - Invoices created (count, total ₪)
     - Client conversations (list)
     - Tasks completed vs pending
  2. Use AI to analyze trends vs previous weeks
  3. Generate insights and recommendations
  4. Create formatted weekly report
  5. Send to me via WhatsApp
  6. Ask: "Anything to add to next week's priorities?"
```

**4. Smart Meeting Preparation**
```
When: 2 hours before meeting (from calendar)
Then:
  1. Query memory for all context about meeting attendees
  2. Find recent conversations, pending items, invoices
  3. Check if any documents were shared
  4. Use AI to create meeting brief:
     - Attendee background
     - Discussion history
     - Open items to address
     - Suggested talking points
  5. Send me prep brief via WhatsApp
  6. Ask: "Need anything else for this meeting?"
```

**5. Project Status Tracker**
```
Every: 3 days
For each: Active project in memory
Do:
  1. Query memory for project context and history
  2. Calculate days since last update
  3. If no update in 7+ days:
     - Send me reminder: "Project X hasn't been updated in 7 days"
     - Ask: "What's the current status?"
  4. When I respond:
     - Update project memory with new status
     - Extract any action items
     - If deadline approaching: create reminder
```

### Personal Productivity

**6. Morning Routine Workflow**
```
Every: Weekday at 7:30am
Do:
  1. Check weather API for Jerusalem
  2. Query memory for today's priorities
  3. Check calendar for meetings (future integration)
  4. Scan for urgent items (overdue invoices, deadlines)
  5. Use AI to create personalized morning brief:
     - Weather summary
     - Top 3 priorities
     - Meeting prep needed
     - Urgent items requiring attention
  6. Send brief via WhatsApp
  7. Ask: "What would you like to focus on first today?"
```

**7. Energy Management Workflow**
```
Every: 2 hours during work day (9am-7pm)
Do:
  1. Send quick check-in: "How's your energy level? (1-10)"
  2. When I respond:
     - Log energy level in memory
     - If level < 5:
       * Suggest: "Time for a break? Coffee? Walk?"
       * Offer to postpone non-urgent tasks
     - If level > 7:
       * Suggest tackling most challenging task
       * Show highest-priority item from memory
  3. Use AI to learn my energy patterns over time
  4. Optimize future suggestions based on patterns
```

**8. Learning & Growth Workflow**
```
Every: Sunday evening
Do:
  1. Query memory for past week's conversations
  2. Use AI to identify:
     - Topics I asked about multiple times
     - Problems I struggled with
     - Skills I wanted to learn
  3. Generate learning recommendations:
     - "You asked about Python async 3 times - want resources?"
     - "You mentioned wanting to improve time management"
  4. Create learning plan with actionable steps
  5. Send to me, ask which to prioritize
  6. Schedule follow-ups to track progress
```

## Technical Design

### 1. Workflow Definition Language

**YAML-based workflow DSL (Domain Specific Language)**

```yaml
# Example: Invoice Follow-up Workflow

workflow:
  name: "Invoice Payment Follow-up"
  id: "workflow-invoice-followup"
  version: "1.0"
  
  triggers:
    - type: event
      event: invoice_created
      filters:
        - field: status
          operator: equals
          value: unpaid
  
  variables:
    - name: invoice_id
      type: string
      source: trigger.invoice_id
    - name: client_name
      type: string
      source: trigger.client_name
    - name: amount
      type: number
      source: trigger.amount
    - name: reminder_count
      type: number
      default: 0
  
  steps:
    - id: wait_initial
      name: "Wait 7 days after invoice creation"
      action: delay
      params:
        duration: 7d
    
    - id: check_status
      name: "Check if invoice is still unpaid"
      action: query_data
      params:
        source: morning_api
        query: get_invoice_status
        invoice_id: "{{ invoice_id }}"
      output: invoice_status
    
    - id: conditional_reminder
      name: "Send reminder if unpaid"
      action: conditional
      condition: "{{ invoice_status == 'unpaid' }}"
      if_true:
        - action: ai_generate
          params:
            template: invoice_reminder
            context:
              client_name: "{{ client_name }}"
              invoice_id: "{{ invoice_id }}"
              amount: "{{ amount }}"
              reminder_number: "{{ reminder_count + 1 }}"
            tone: polite_professional
          output: reminder_message
        
        - action: send_whatsapp
          params:
            recipient: "{{ client_name }}"
            message: "{{ reminder_message }}"
        
        - action: update_memory
          params:
            type: append
            key: "invoice:{{ invoice_id }}:reminders"
            value: "Reminder sent on {{ now }}"
        
        - action: set_variable
          params:
            name: reminder_count
            value: "{{ reminder_count + 1 }}"
        
        - action: wait
          params:
            duration: 7d
        
        - action: goto
          params:
            step_id: check_status
      
      if_false:
        - action: log
          params:
            message: "Invoice {{ invoice_id }} paid, workflow complete"
        - action: end_workflow
    
    - id: escalate_to_godfather
      name: "Notify godfather after multiple reminders"
      action: conditional
      condition: "{{ reminder_count >= 2 }}"
      if_true:
        - action: send_whatsapp
          params:
            recipient: godfather
            message: |
              ⚠️ Invoice {{ invoice_id }} to {{ client_name }} (₪{{ amount }}) 
              is still unpaid after {{ reminder_count }} reminders.
              
              Would you like me to:
              1. Send final notice
              2. Mark as seriously overdue
              3. Schedule call with client
        
        - action: wait_for_response
          params:
            timeout: 24h
          output: godfather_decision
        
        - action: ai_execute
          params:
            instruction: "{{ godfather_decision }}"
            available_actions:
              - send_whatsapp
              - update_invoice_status
              - create_schedule
              - update_memory
```

### 2. Workflow Engine Architecture

```python
# src/workflows/engine.py

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"      # Waiting for delay or user input
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class WorkflowExecution:
    execution_id: str
    workflow_id: str
    status: WorkflowStatus
    current_step: str
    variables: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    trigger_data: Dict[str, Any]
    history: List[Dict]
    error: Optional[str] = None

class WorkflowEngine:
    """Execute and manage workflow instances."""
    
    def __init__(
        self,
        action_registry: ActionRegistry,
        memory_manager: MemoryManager,
        whatsapp_handler: WhatsAppHandler,
        ai_handler: AIHandler
    ):
        self.actions = action_registry
        self.memory = memory_manager
        self.whatsapp = whatsapp_handler
        self.ai = ai_handler
        self.executions: Dict[str, WorkflowExecution] = {}
        self.workflows: Dict[str, Workflow] = {}
    
    async def execute_workflow(
        self,
        workflow_id: str,
        trigger_data: Dict[str, Any]
    ) -> str:
        """Start a new workflow execution."""
        
        workflow = self.workflows[workflow_id]
        execution_id = str(uuid4())
        
        # Initialize execution context
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            current_step=workflow.steps[0].id,
            variables=self._initialize_variables(workflow, trigger_data),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            trigger_data=trigger_data,
            history=[]
        )
        
        self.executions[execution_id] = execution
        
        # Execute workflow in background
        asyncio.create_task(self._run_workflow(execution))
        
        return execution_id
    
    async def _run_workflow(self, execution: WorkflowExecution):
        """Run workflow steps sequentially."""
        
        workflow = self.workflows[execution.workflow_id]
        
        try:
            step_index = 0
            
            while step_index < len(workflow.steps):
                step = workflow.steps[step_index]
                execution.current_step = step.id
                execution.updated_at = datetime.now()
                
                logger.info(f"Executing step {step.id} in workflow {workflow.name}")
                
                # Execute step
                result = await self._execute_step(step, execution)
                
                # Log step execution
                execution.history.append({
                    "step_id": step.id,
                    "timestamp": datetime.now(),
                    "result": result,
                    "status": "success"
                })
                
                # Handle step result
                if result.get("action") == "goto":
                    # Jump to different step
                    target_step = result["step_id"]
                    step_index = self._find_step_index(workflow, target_step)
                
                elif result.get("action") == "end_workflow":
                    # End workflow early
                    break
                
                elif result.get("action") == "wait":
                    # Pause workflow
                    execution.status = WorkflowStatus.WAITING
                    await asyncio.sleep(result["duration_seconds"])
                    execution.status = WorkflowStatus.RUNNING
                
                elif result.get("action") == "wait_for_response":
                    # Wait for user input
                    execution.status = WorkflowStatus.WAITING
                    response = await self._wait_for_user_response(
                        execution,
                        timeout=result.get("timeout_seconds", 86400)
                    )
                    execution.variables[result.get("output")] = response
                    execution.status = WorkflowStatus.RUNNING
                
                # Move to next step
                step_index += 1
            
            # Workflow completed
            execution.status = WorkflowStatus.COMPLETED
            logger.info(f"Workflow {workflow.name} completed successfully")
        
        except Exception as e:
            # Workflow failed
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            logger.error(f"Workflow {workflow.name} failed: {e}")
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Execute a single workflow step."""
        
        action_type = step.action
        params = self._resolve_params(step.params, execution.variables)
        
        # Get action handler
        action_handler = self.actions.get(action_type)
        
        # Execute action
        result = await action_handler.execute(params, execution)
        
        # Store output variable if specified
        if step.output:
            execution.variables[step.output] = result
        
        return result
    
    def _resolve_params(
        self,
        params: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve template variables in parameters."""
        
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and "{{" in value:
                # Template variable - resolve it
                resolved[key] = self._evaluate_template(value, variables)
            else:
                resolved[key] = value
        
        return resolved
    
    def _evaluate_template(self, template: str, variables: Dict[str, Any]) -> Any:
        """Evaluate a template string with variables."""
        
        # Simple template evaluation: {{ variable_name }}
        # For production, use Jinja2 or similar
        
        import re
        
        pattern = r'\{\{\s*([^}]+)\s*\}\}'
        
        def replace(match):
            var_name = match.group(1).strip()
            
            # Handle expressions like "reminder_count + 1"
            if any(op in var_name for op in ['+', '-', '*', '/', '==', '!=']):
                return str(eval(var_name, {"__builtins__": {}}, variables))
            
            # Simple variable lookup
            return str(variables.get(var_name, ''))
        
        return re.sub(pattern, replace, template)
    
    async def _wait_for_user_response(
        self,
        execution: WorkflowExecution,
        timeout: int
    ) -> str:
        """Wait for user to respond to workflow."""
        
        # Store execution as waiting for response
        # When user sends message, check if it's a response to this workflow
        # Return the user's message
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            # Check for pending response
            response = self._get_pending_response(execution.execution_id)
            if response:
                return response
            
            await asyncio.sleep(1)
        
        raise TimeoutError(f"No response received within {timeout} seconds")
```

### 3. Action Registry

```python
# src/workflows/actions.py

class Action:
    """Base class for workflow actions."""
    
    async def execute(
        self,
        params: Dict[str, Any],
        execution: WorkflowExecution
    ) -> Any:
        raise NotImplementedError

class ActionRegistry:
    """Registry of available workflow actions."""
    
    def __init__(self):
        self.actions: Dict[str, Action] = {}
    
    def register(self, name: str, action: Action):
        self.actions[name] = action
    
    def get(self, name: str) -> Action:
        return self.actions[name]

# Built-in actions

class DelayAction(Action):
    """Pause workflow for specified duration."""
    
    async def execute(self, params: Dict, execution: WorkflowExecution) -> Dict:
        duration_str = params["duration"]  # e.g., "7d", "2h", "30m"
        seconds = self._parse_duration(duration_str)
        
        return {
            "action": "wait",
            "duration_seconds": seconds
        }
    
    def _parse_duration(self, duration: str) -> int:
        """Parse duration string to seconds."""
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        value = int(duration[:-1])
        unit = duration[-1]
        return value * units[unit]

class SendWhatsAppAction(Action):
    """Send WhatsApp message."""
    
    def __init__(self, whatsapp_handler: WhatsAppHandler):
        self.whatsapp = whatsapp_handler
    
    async def execute(self, params: Dict, execution: WorkflowExecution) -> Dict:
        recipient = params["recipient"]
        message = params["message"]
        
        # Resolve recipient (could be name, phone, or "godfather")
        chat_id = self._resolve_recipient(recipient)
        
        # Send message
        self.whatsapp.send_message(chat_id, message)
        
        return {"status": "sent", "recipient": recipient}

class AIGenerateAction(Action):
    """Generate content using AI."""
    
    def __init__(self, ai_handler: AIHandler, memory_manager: MemoryManager):
        self.ai = ai_handler
        self.memory = memory_manager
    
    async def execute(self, params: Dict, execution: WorkflowExecution) -> str:
        template = params.get("template")
        context = params.get("context", {})
        tone = params.get("tone", "professional")
        
        # Build AI prompt
        prompt = self._build_prompt(template, context, tone)
        
        # Generate with AI
        response = self.ai.create_request(
            system_message=f"Generate message with {tone} tone",
            user_message=prompt
        )
        
        return response.content

class QueryMemoryAction(Action):
    """Query persistent memory."""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
    
    async def execute(self, params: Dict, execution: WorkflowExecution) -> Any:
        query = params["query"]
        filters = params.get("filters", {})
        
        # Query memory
        results = self.memory.query(query, **filters)
        
        return results

class ConditionalAction(Action):
    """Execute conditional logic."""
    
    async def execute(self, params: Dict, execution: WorkflowExecution) -> Dict:
        condition = params["condition"]
        
        # Evaluate condition
        is_true = self._evaluate_condition(condition, execution.variables)
        
        if is_true:
            # Return if_true branch actions
            return {
                "action": "execute_branch",
                "branch": params["if_true"]
            }
        else:
            # Return if_false branch actions
            return {
                "action": "execute_branch",
                "branch": params.get("if_false", [])
            }

class AIExecuteAction(Action):
    """Let AI determine and execute actions based on instruction."""
    
    def __init__(
        self,
        ai_handler: AIHandler,
        action_registry: ActionRegistry
    ):
        self.ai = ai_handler
        self.actions = action_registry
    
    async def execute(self, params: Dict, execution: WorkflowExecution) -> Dict:
        instruction = params["instruction"]
        available_actions = params["available_actions"]
        
        # Use AI to plan action sequence
        prompt = f"""
        User instruction: {instruction}
        
        Available actions: {available_actions}
        
        Current context: {execution.variables}
        
        Determine the appropriate action(s) to take and return as JSON.
        """
        
        response = self.ai.create_request(
            system_message="You are a workflow execution planner",
            user_message=prompt,
            response_format={"type": "json_object"}
        )
        
        plan = json.loads(response.content)
        
        # Execute planned actions
        for action in plan["actions"]:
            action_handler = self.actions.get(action["type"])
            await action_handler.execute(action["params"], execution)
        
        return {"status": "completed", "actions_executed": len(plan["actions"])}
```

### 4. Natural Language Workflow Builder

```python
# src/workflows/builder.py

class WorkflowBuilder:
    """Build workflows from natural language descriptions."""
    
    def __init__(self, ai_handler: AIHandler):
        self.ai = ai_handler
    
    async def build_from_description(
        self,
        description: str,
        user_id: str
    ) -> Workflow:
        """Convert natural language to workflow definition."""
        
        # Use AI to parse description into structured workflow
        prompt = f"""
        Convert this workflow description into a structured workflow definition:
        
        "{description}"
        
        Return a YAML workflow definition with:
        - Workflow name and metadata
        - Trigger configuration
        - Variables needed
        - Step-by-step actions
        - Conditional logic
        - Error handling
        
        Use these available actions:
        - delay: Wait for duration
        - send_whatsapp: Send WhatsApp message
        - ai_generate: Generate content with AI
        - query_memory: Query persistent memory
        - update_memory: Store information
        - query_data: Query external APIs
        - conditional: If/else logic
        - ai_execute: Let AI decide actions
        - wait_for_response: Wait for user input
        
        Be specific and include all necessary parameters.
        """
        
        response = self.ai.create_request(
            model="gpt-4o",
            system_message="You are a workflow design expert",
            user_message=prompt
        )
        
        # Parse YAML workflow
        workflow_yaml = response.content
        workflow_dict = yaml.safe_load(workflow_yaml)
        
        # Validate workflow
        validated = self._validate_workflow(workflow_dict)
        
        # Create Workflow object
        workflow = Workflow.from_dict(validated)
        workflow.created_by = user_id
        
        return workflow
    
    def _validate_workflow(self, workflow_dict: Dict) -> Dict:
        """Validate workflow definition."""
        
        # Check required fields
        required = ["workflow", "triggers", "steps"]
        for field in required:
            if field not in workflow_dict:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate steps
        for step in workflow_dict["steps"]:
            if "id" not in step or "action" not in step:
                raise ValueError("Each step must have id and action")
        
        return workflow_dict
    
    async def enhance_workflow(
        self,
        workflow: Workflow,
        enhancement_request: str
    ) -> Workflow:
        """Enhance existing workflow based on request."""
        
        prompt = f"""
        Current workflow:
        {workflow.to_yaml()}
        
        Enhancement request: {enhancement_request}
        
        Return the enhanced workflow definition in YAML.
        Maintain existing functionality while adding the requested enhancements.
        """
        
        response = self.ai.create_request(
            model="gpt-4o",
            system_message="You are a workflow enhancement expert",
            user_message=prompt
        )
        
        enhanced_yaml = response.content
        enhanced_dict = yaml.safe_load(enhanced_yaml)
        
        return Workflow.from_dict(enhanced_dict)
```

### 5. Workflow Templates Library

```python
# Pre-built workflow templates

WORKFLOW_TEMPLATES = {
    "invoice_followup": {
        "name": "Invoice Payment Follow-up",
        "description": "Automated reminders for unpaid invoices",
        "customizable": ["reminder_intervals", "escalation_threshold", "message_tone"],
        "yaml": "..." # Full YAML definition
    },
    
    "client_onboarding": {
        "name": "Client Onboarding Process",
        "description": "Welcome new clients and set up their account",
        "customizable": ["welcome_message", "checkin_frequency", "onboarding_duration"],
        "yaml": "..."
    },
    
    "weekly_review": {
        "name": "Weekly Performance Review",
        "description": "Analyze week's activities and generate insights",
        "customizable": ["review_day", "review_time", "metrics_to_track"],
        "yaml": "..."
    },
    
    "project_tracker": {
        "name": "Project Status Tracker",
        "description": "Monitor project progress and send reminders",
        "customizable": ["check_frequency", "inactivity_threshold", "projects_to_track"],
        "yaml": "..."
    },
    
    "morning_briefing": {
        "name": "Daily Morning Briefing",
        "description": "Personalized morning summary and priorities",
        "customizable": ["briefing_time", "days_of_week", "content_sections"],
        "yaml": "..."
    }
}

class WorkflowTemplateManager:
    """Manage workflow templates."""
    
    def list_templates(self) -> List[Dict]:
        """List available templates."""
        return [
            {
                "id": tid,
                "name": t["name"],
                "description": t["description"]
            }
            for tid, t in WORKFLOW_TEMPLATES.items()
        ]
    
    def instantiate_template(
        self,
        template_id: str,
        customizations: Dict[str, Any]
    ) -> Workflow:
        """Create workflow from template with customizations."""
        
        template = WORKFLOW_TEMPLATES[template_id]
        workflow_dict = yaml.safe_load(template["yaml"])
        
        # Apply customizations
        for key, value in customizations.items():
            self._apply_customization(workflow_dict, key, value)
        
        return Workflow.from_dict(workflow_dict)
```

### 6. Godfather Interface

```python
# User commands for workflow management

# Create workflow from natural language
"Create workflow: When invoice is created, wait 7 days, then send payment reminder"

# Use template
"Create invoice follow-up workflow with reminders every 5 days"

# List workflows
"/workflows" or "Show my workflows"

# Enable/disable workflow
"/workflow pause invoice-followup"
"/workflow enable morning-briefing"

# Edit workflow
"Edit workflow morning-briefing: change time to 8am"

# Delete workflow
"/workflow delete project-tracker"

# View workflow details
"/workflow show invoice-followup"

# Test workflow
"/workflow test weekly-review"
```

## Storage Schema

```json
// state/workflows.json
{
  "workflow-uuid-1": {
    "id": "workflow-uuid-1",
    "name": "Invoice Payment Follow-up",
    "version": "1.0",
    "created_by": "972501234567@c.us",
    "created_at": "2026-01-17T10:00:00Z",
    "enabled": true,
    "triggers": [...],
    "steps": [...],
    "variables": [...]
  }
}

// state/workflow_executions.json
{
  "execution-uuid-1": {
    "execution_id": "execution-uuid-1",
    "workflow_id": "workflow-uuid-1",
    "status": "waiting",
    "current_step": "wait_for_response",
    "variables": {
      "invoice_id": "INV-001",
      "client_name": "Tech Corp",
      "amount": 5000,
      "reminder_count": 1
    },
    "created_at": "2026-01-17T10:00:00Z",
    "updated_at": "2026-01-17T10:15:00Z",
    "history": [...]
  }
}
```

## Implementation Plan

### Phase 1: Core Engine
- [ ] Implement Workflow and WorkflowStep models
- [ ] Create WorkflowEngine with basic execution
- [ ] Implement ActionRegistry
- [ ] Build core actions: delay, send_whatsapp, conditional
- [ ] Test simple linear workflows

### Phase 2: Advanced Actions
- [ ] Implement AI actions: ai_generate, ai_execute
- [ ] Add memory actions: query_memory, update_memory
- [ ] Add data query actions for external APIs
- [ ] Implement wait_for_response for user input
- [ ] Test complex multi-step workflows

### Phase 3: Natural Language Builder
- [ ] Create WorkflowBuilder with AI parsing
- [ ] Implement workflow validation
- [ ] Add workflow enhancement
- [ ] Test NL-to-workflow conversion accuracy

### Phase 4: Templates & Library
- [ ] Create 5 core workflow templates
- [ ] Implement template customization
- [ ] Build template discovery/browsing
- [ ] Test template instantiation

### Phase 5: Management Interface
- [ ] Add workflow management commands
- [ ] Implement workflow pause/resume
- [ ] Create workflow analytics/monitoring
- [ ] Build workflow debugging tools

### Phase 6: Advanced Features
- [ ] Error handling and retry logic
- [ ] Workflow versioning
- [ ] Workflow scheduling optimization
- [ ] Multi-workflow coordination

## Dependencies

```python
# requirements.txt additions
PyYAML>=6.0.1              # YAML parsing
croniter>=2.0.0            # Cron scheduling
jinja2>=3.1.0              # Template engine
pydantic>=2.0.0            # Data validation
```

## Example Workflows in Action

### Example 1: Invoice Follow-up

```
Godfather: "Create a workflow: when I create an invoice, wait 7 days, 
then send a polite reminder if it's still unpaid"

Bot: "✅ Created workflow 'Invoice Follow-up'

Triggers: When invoice is created (status: unpaid)
Actions:
1. Wait 7 days
2. Check invoice status
3. If still unpaid → Send polite reminder
4. If still unpaid after 14 days → Notify you

Would you like to customize the reminder messages or timing?"

[7 days later, after invoice creation]

Bot → Client: "Hi Sarah! Just a friendly reminder about invoice 
INV-001 (₪5,000) from January 10th. Let me know if you have 
any questions! 😊"

[14 days later, if still unpaid]

Bot → Godfather: "⚠️ Invoice INV-001 to Tech Corp (₪5,000) is 
still unpaid after 2 reminders. What would you like to do?"
```

### Example 2: Weekly Review

```
Godfather: "Every Friday at 4pm, analyze my week and send me a summary"

Bot: "✅ Created workflow 'Weekly Review'

Schedule: Every Friday at 4:00 PM
Actions:
1. Query this week's activities from memory
2. Analyze invoices, conversations, tasks
3. Compare to previous weeks
4. Generate insights with AI
5. Send comprehensive report to you

First report will be this Friday. Want a preview now?"

[Friday at 4pm]

Bot → Godfather: "📊 Week of January 13-17, 2026

**Invoices** 
• Created: 8 (₪42,500 total)
• Paid: 5 (₪28,000)
• Pending: 3 (₪14,500)
• Trend: ⬆️ 15% vs last week

**Client Activity**
• Conversations: 12 clients
• New leads: 2 (ABC Corp, XYZ Ltd)
• Follow-ups needed: 3

**Tasks**
• Completed: 8/10 (80%)
• Carry over: 2 to next week

**Insights**
• Friday is your most productive invoice day (4 invoices)
• Response time to clients improved by 2 hours
• Revenue on track for monthly goal (71% with 50% of month elapsed)

What would you like to focus on next week?"
```

### Example 3: Smart Project Check-in

```
Godfather: "Track Project Alpha - if I don't mention it for 3 days, 
remind me to give an update"

Bot: "✅ Created workflow 'Project Alpha Tracker'

Monitoring: Mentions of 'Project Alpha' in conversations
Trigger: No mention for 3 days → Send reminder
Actions:
• Track last mention in memory
• After 3 days of silence → Ask for update
• When you respond → Update project memory
• Extract action items automatically

Currently tracking. Last mention: Today at 2:30 PM"

[3 days later, no Project Alpha mentions]

Bot → Godfather: "Hey! It's been 3 days since we discussed Project Alpha. 
Last update: You were working on the API integration with deadline March 1st. 

How's it progressing?"

Godfather: "Good progress - API integration is 80% done. Just need to 
add authentication and we're ready for testing"

Bot: "✅ Updated Project Alpha memory:
• Status: API integration 80% complete
• Next: Add authentication
• Phase: Ready for testing soon
• Last updated: January 20, 2026

Should I remind you about testing in 3 days?"
```

## Success Metrics

- ✅ Godfather can create workflows via natural language
- ✅ 95%+ workflow execution reliability
- ✅ AI accurately converts descriptions to workflows
- ✅ Workflows execute within 10% of scheduled time
- ✅ 5+ workflow templates available and tested
- ✅ Workflow debugging is straightforward
- ✅ 90%+ test coverage for workflow engine

## Security & Privacy

- **Authorization**: Only Godfather and Admin can create workflows
- **Validation**: All workflow definitions validated before execution
- **Sandboxing**: Actions run in controlled environment
- **Rate Limiting**: Max 50 active workflows per user
- **Audit Trail**: Complete history of all workflow executions
- **Rollback**: Ability to cancel/rollback workflow executions
- **Data Access**: Workflows respect RBAC permissions

## Testing Strategy

### Unit Tests
- Workflow parser and validator
- Individual action handlers
- Template variable resolution
- Conditional logic evaluation

### Integration Tests
- End-to-end workflow execution
- Multi-step workflows with delays
- Error handling and recovery
- AI-driven action execution

### Manual Tests
1. Create workflow from natural language
2. Execute simple 3-step workflow
3. Test conditional branching
4. Verify user input waiting
5. Test template customization
6. Monitor long-running workflow (7+ days)

## Future Enhancements

- **Visual Workflow Builder**: Drag-and-drop workflow designer
- **Workflow Marketplace**: Share workflows with other users
- **Advanced Analytics**: Workflow performance metrics, optimization suggestions
- **Multi-User Workflows**: Coordinate workflows across team members
- **External Integrations**: Connect to Zapier, Make.com, n8n
- **Workflow Testing**: Sandbox mode for testing workflows
- **Version Control**: Track workflow changes, rollback to previous versions
- **Smart Recommendations**: AI suggests workflows based on usage patterns
- **Workflow Composition**: Combine multiple workflows into larger processes
- **Real-time Debugging**: Step through workflow execution in real-time

## Comparison to Existing Tools

| Feature | DeniDin Workflows | Zapier | Make.com | Spec Kit |
|---------|------------------|---------|----------|----------|
| **Natural Language Creation** | ✅ Full AI | ❌ GUI only | ❌ GUI only | ✅ Code only |
| **AI Decision Making** | ✅ Built-in | ❌ Limited | ❌ Limited | ✅ Full |
| **WhatsApp Native** | ✅ Yes | 🔶 Via API | 🔶 Via API | ❌ No |
| **Memory Integration** | ✅ Deep | ❌ No | ❌ No | ❌ No |
| **Conversational UI** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **Agentic Execution** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **Cost** | Free | $$$ | $$$ | $ |

**Key Differentiator**: DeniDin Workflows uniquely combine:
1. Natural language workflow creation
2. Agentic AI decision-making within workflows
3. Deep integration with persistent memory
4. Native WhatsApp conversational interface
5. Purpose-built for Godfather's business processes

This is NOT a generic automation tool - it's an **intelligent business assistant** that understands context, learns patterns, and makes smart decisions within defined workflows.

## Dependencies on Other Features

- **Required**: Feature 004 (MCP WhatsApp) - Send messages from workflows
- **Required**: Feature 006 (RBAC) - Workflow authorization
- **Required**: Feature 007 (Memory) - Context for AI actions
- **Enhanced by**: Feature 005 (Green Receipt) - Invoice workflow triggers
- **Enhanced by**: Feature 008 (Scheduled Chats) - Time-based workflow triggers
- **Enhanced by**: Feature 003 (Media Processing) - Process documents in workflows

---

**Next Steps**:
1. Review and approve spec
2. Decide on implementation priority
3. Start with Phase 1 (Core Engine)
4. Build 2-3 simple workflows as proof of concept
5. Iterate based on real usage patterns
