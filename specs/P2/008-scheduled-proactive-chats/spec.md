# Feature Spec: Scheduled Proactive Chat Initiations

**Feature ID**: 008-scheduled-proactive-chats  
**Priority**: P1 (High)  
**Status**: Planning  
**Created**: January 17, 2026

## Problem Statement

Currently, DeniDin is purely reactive - it only responds when users send messages. The system cannot:
- Initiate conversations on its own
- Send scheduled reminders or check-ins
- Proactively surface important information
- Engage the Godfather with daily/weekly summaries or prompts

**Desired Capabilities:**

**Time-Based Triggers:**
- Daily morning briefing: "Good morning! Here's your schedule for today..."
- Weekly review: "It's Friday - let's review the week's progress"
- Custom schedules: "Every Monday at 9am, ask about project status"

**Godfather-Defined Triggers:**
- "Remind me every day at 8am to review invoices"
- "Every Friday afternoon, ask me about next week's priorities"
- "On the 1st of each month, prompt me for expense review"
- "Every 3 days, check in on Project Alpha progress"

**Smart Triggers:**
- Event-based: "When invoice becomes overdue, notify me"
- Condition-based: "If no activity for 48 hours, send check-in"
- Context-aware: "Before important meetings, send prep reminder"

## Use Cases

### Daily Routines
1. **Morning Briefing**: "Good morning! You have 3 meetings today and 2 overdue invoices."
2. **Evening Summary**: "End of day recap: 5 messages handled, 2 invoices created."
3. **Habit Tracking**: "Did you complete your daily exercise goal?"

### Weekly Routines
4. **Week Planning**: Monday 9am - "Let's plan this week's priorities"
5. **Progress Check**: Wednesday - "How are your weekly goals progressing?"
6. **Week Review**: Friday 5pm - "Week completed! What were your wins?"

### Custom Schedules
7. **Project Check-ins**: "It's been 3 days - update on Project Alpha?"
8. **Client Follow-ups**: "Follow up with Sarah about proposal?"
9. **Financial Reviews**: Monthly - "Review this month's revenue and expenses"

### Event-Driven
10. **Overdue Alerts**: "Invoice #123 is now 7 days overdue"
11. **Milestone Reminders**: "Project deadline is in 3 days"
12. **Inactivity Check**: "Haven't heard from you in 2 days - everything okay?"

## Technical Design

### 1. Data Model

```python
# src/models/schedule.py

from enum import Enum
from datetime import datetime, time
from typing import Optional, List, Union

class TriggerType(str, Enum):
    CRON = "cron"              # Cron-like schedule
    INTERVAL = "interval"      # Every N hours/days
    TIME_OF_DAY = "time_of_day" # Specific time daily
    DAY_OF_WEEK = "day_of_week" # Specific day(s) weekly
    DAY_OF_MONTH = "day_of_month" # Specific day monthly
    EVENT = "event"            # Event-driven trigger
    CONDITION = "condition"    # Condition-based trigger

class ScheduledChat:
    schedule_id: str                # UUID
    user_id: str                    # Target user (Godfather)
    chat_id: str                    # WhatsApp chat ID
    
    # Trigger configuration
    trigger_type: TriggerType
    trigger_config: dict            # Depends on trigger_type
    
    # Message configuration
    message_template: str           # What to send
    message_type: str               # "static" or "dynamic"
    prompt_for_ai: Optional[str]    # If dynamic, AI prompt
    
    # Metadata
    name: str                       # Human-readable name
    description: str
    enabled: bool
    created_at: datetime
    last_triggered: Optional[datetime]
    next_trigger: Optional[datetime]
    
    # Limits and controls
    max_triggers: Optional[int]     # Stop after N triggers
    trigger_count: int
    timezone: str                   # "Asia/Jerusalem", etc.
    
    # Conditions
    conditions: List[dict]          # Additional conditions to check
```

### 2. Trigger Types Configuration

```python
# Trigger Config Examples

# 1. CRON (Most flexible)
{
    "trigger_type": "cron",
    "trigger_config": {
        "cron": "0 8 * * *"  # Every day at 8:00 AM
    }
}

# 2. TIME_OF_DAY
{
    "trigger_type": "time_of_day",
    "trigger_config": {
        "time": "08:00",      # 8:00 AM
        "days": ["mon", "tue", "wed", "thu", "fri"]  # Weekdays only
    }
}

# 3. INTERVAL
{
    "trigger_type": "interval",
    "trigger_config": {
        "interval_hours": 72,  # Every 3 days
        "start_time": "09:00"  # At 9 AM
    }
}

# 4. DAY_OF_WEEK
{
    "trigger_type": "day_of_week",
    "trigger_config": {
        "days": ["monday"],
        "time": "09:00"
    }
}

# 5. DAY_OF_MONTH
{
    "trigger_type": "day_of_month",
    "trigger_config": {
        "day": 1,          # 1st of month
        "time": "09:00"
    }
}

# 6. EVENT (Webhook/condition-based)
{
    "trigger_type": "event",
    "trigger_config": {
        "event_name": "invoice_overdue",
        "event_params": {
            "days_overdue": 7
        }
    }
}

# 7. CONDITION (Check periodically)
{
    "trigger_type": "condition",
    "trigger_config": {
        "check_interval_hours": 1,
        "condition": "no_activity_for_hours > 48"
    }
}
```

### 3. Message Templates

```python
# Static message
{
    "message_type": "static",
    "message_template": "Good morning! Time to review today's priorities."
}

# Dynamic AI-generated message
{
    "message_type": "dynamic",
    "prompt_for_ai": """
    Generate a morning briefing including:
    - Weather summary
    - Today's date and day of week
    - Motivational quote
    - Ask about priorities for today
    """
}

# Context-aware dynamic message
{
    "message_type": "dynamic",
    "prompt_for_ai": """
    Check the Godfather's memory for:
    - Upcoming deadlines this week
    - Overdue invoices
    - Recent project discussions
    
    Create a friendly check-in message asking about progress
    on the most relevant items.
    """
}

# Templated with variables
{
    "message_type": "template",
    "message_template": """
    🗓️ {day_of_week} Morning Check-in
    
    Today is {date}
    
    Pending tasks from memory:
    {pending_tasks}
    
    What would you like to focus on today?
    """
}
```

### 4. Scheduler Implementation

```python
# src/utils/scheduler.py

import schedule
from datetime import datetime, time
from croniter import croniter
import pytz

class ChatScheduler:
    def __init__(
        self,
        schedule_manager: ScheduleManager,
        whatsapp_handler: WhatsAppHandler,
        ai_handler: AIHandler,
        memory_manager: MemoryManager
    ):
        self.schedule_manager = schedule_manager
        self.whatsapp = whatsapp_handler
        self.ai = ai_handler
        self.memory = memory_manager
        self.timezone = pytz.timezone("Asia/Jerusalem")
    
    def start(self):
        """Start the scheduler loop."""
        logger.info("Chat scheduler started")
        
        # Load all schedules
        self.reload_schedules()
        
        # Run schedule check every minute
        schedule.every(1).minutes.do(self.check_triggers)
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    
    def reload_schedules(self):
        """Reload all active schedules."""
        schedules = self.schedule_manager.get_active_schedules()
        
        for sched in schedules:
            self.register_schedule(sched)
        
        logger.info(f"Loaded {len(schedules)} active schedules")
    
    def register_schedule(self, sched: ScheduledChat):
        """Register a schedule with the scheduler."""
        
        if sched.trigger_type == TriggerType.CRON:
            # Use croniter for cron-like schedules
            self._register_cron(sched)
        
        elif sched.trigger_type == TriggerType.TIME_OF_DAY:
            self._register_time_of_day(sched)
        
        elif sched.trigger_type == TriggerType.INTERVAL:
            self._register_interval(sched)
        
        # ... other trigger types
    
    def _register_cron(self, sched: ScheduledChat):
        """Register cron-based schedule."""
        cron_expr = sched.trigger_config["cron"]
        
        def job():
            self.execute_schedule(sched)
        
        # Calculate next run time
        cron = croniter(cron_expr, datetime.now(self.timezone))
        next_run = cron.get_next(datetime)
        
        schedule.every().day.at(
            next_run.strftime("%H:%M")
        ).do(job).tag(sched.schedule_id)
    
    def _register_time_of_day(self, sched: ScheduledChat):
        """Register time-of-day schedule."""
        target_time = sched.trigger_config["time"]
        days = sched.trigger_config.get("days", ["all"])
        
        def job():
            # Check if today matches
            today = datetime.now(self.timezone).strftime("%a").lower()[:3]
            if days == ["all"] or today in days:
                self.execute_schedule(sched)
        
        schedule.every().day.at(target_time).do(job).tag(sched.schedule_id)
    
    def _register_interval(self, sched: ScheduledChat):
        """Register interval-based schedule."""
        hours = sched.trigger_config["interval_hours"]
        
        def job():
            self.execute_schedule(sched)
        
        schedule.every(hours).hours.do(job).tag(sched.schedule_id)
    
    def check_triggers(self):
        """Check condition-based and event-based triggers."""
        
        schedules = self.schedule_manager.get_schedules_by_type([
            TriggerType.EVENT,
            TriggerType.CONDITION
        ])
        
        for sched in schedules:
            if self._check_trigger_condition(sched):
                self.execute_schedule(sched)
    
    def _check_trigger_condition(self, sched: ScheduledChat) -> bool:
        """Check if trigger condition is met."""
        
        if sched.trigger_type == TriggerType.CONDITION:
            condition = sched.trigger_config["condition"]
            
            # Example: no_activity_for_hours > 48
            if "no_activity_for_hours" in condition:
                user = user_manager.get_user(sched.user_id)
                hours_since_activity = (
                    datetime.now() - user.last_active
                ).total_seconds() / 3600
                
                threshold = int(condition.split(">")[1].strip())
                return hours_since_activity > threshold
        
        elif sched.trigger_type == TriggerType.EVENT:
            # Check event conditions (e.g., invoice overdue)
            event_name = sched.trigger_config["event_name"]
            
            if event_name == "invoice_overdue":
                # Query Morning API for overdue invoices
                # Return True if any found
                pass
        
        return False
    
    def execute_schedule(self, sched: ScheduledChat):
        """Execute a scheduled chat."""
        
        logger.info(f"Executing schedule: {sched.name}")
        
        # Check if max triggers reached
        if sched.max_triggers and sched.trigger_count >= sched.max_triggers:
            logger.info(f"Schedule {sched.schedule_id} reached max triggers")
            self.schedule_manager.disable_schedule(sched.schedule_id)
            return
        
        # Generate message
        message = self._generate_message(sched)
        
        # Send via WhatsApp
        try:
            self.whatsapp.send_message(sched.chat_id, message)
            
            # Update schedule
            self.schedule_manager.record_trigger(sched.schedule_id)
            
            logger.info(f"Schedule executed successfully: {sched.name}")
            
        except Exception as e:
            logger.error(f"Failed to execute schedule {sched.schedule_id}: {e}")
    
    def _generate_message(self, sched: ScheduledChat) -> str:
        """Generate message based on schedule config."""
        
        if sched.message_type == "static":
            return sched.message_template
        
        elif sched.message_type == "dynamic":
            # Use AI to generate message
            prompt = sched.prompt_for_ai
            
            # Add context from memory
            memory_context = self.memory.recall(
                query=prompt,
                chat_id=sched.chat_id,
                user_id=sched.user_id,
                is_godfather=True
            )
            
            # Generate with AI
            response = self.ai.create_request(
                system_message=f"You are initiating a proactive check-in.\n\n{memory_context}",
                user_message=prompt
            )
            
            return response.content
        
        elif sched.message_type == "template":
            # Fill in template variables
            template = sched.message_template
            
            variables = {
                "day_of_week": datetime.now(self.timezone).strftime("%A"),
                "date": datetime.now(self.timezone).strftime("%B %d, %Y"),
                "pending_tasks": self._get_pending_tasks(sched)
            }
            
            return template.format(**variables)
        
        return sched.message_template
    
    def _get_pending_tasks(self, sched: ScheduledChat) -> str:
        """Retrieve pending tasks from memory."""
        # Query memory for pending items
        # Return formatted list
        return "• Review Project Alpha\n• Follow up with Sarah"
```

### 5. Schedule Manager

```python
# src/utils/schedule_manager.py

class ScheduleManager:
    def __init__(self, storage_path: str = "state/schedules.json"):
        self.storage_path = storage_path
        self.schedules: Dict[str, ScheduledChat] = {}
        self.load_schedules()
    
    def create_schedule(
        self,
        user_id: str,
        chat_id: str,
        name: str,
        trigger_type: TriggerType,
        trigger_config: dict,
        message_template: str,
        **kwargs
    ) -> ScheduledChat:
        """Create a new scheduled chat."""
        
        schedule = ScheduledChat(
            schedule_id=str(uuid4()),
            user_id=user_id,
            chat_id=chat_id,
            name=name,
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            message_template=message_template,
            enabled=True,
            created_at=datetime.now(),
            trigger_count=0,
            **kwargs
        )
        
        self.schedules[schedule.schedule_id] = schedule
        self.save_schedules()
        
        return schedule
    
    def get_active_schedules(self) -> List[ScheduledChat]:
        """Get all enabled schedules."""
        return [s for s in self.schedules.values() if s.enabled]
    
    def disable_schedule(self, schedule_id: str):
        """Disable a schedule."""
        if schedule_id in self.schedules:
            self.schedules[schedule_id].enabled = False
            self.save_schedules()
    
    def delete_schedule(self, schedule_id: str):
        """Delete a schedule."""
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            self.save_schedules()
    
    def record_trigger(self, schedule_id: str):
        """Record that a schedule was triggered."""
        if schedule_id in self.schedules:
            sched = self.schedules[schedule_id]
            sched.last_triggered = datetime.now()
            sched.trigger_count += 1
            self.save_schedules()
    
    def load_schedules(self):
        """Load schedules from storage."""
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.schedules = {
                    sid: ScheduledChat(**sdata)
                    for sid, sdata in data.items()
                }
    
    def save_schedules(self):
        """Save schedules to storage."""
        with open(self.storage_path, 'w') as f:
            json.dump(
                {sid: s.dict() for sid, s in self.schedules.items()},
                f,
                indent=2,
                default=str
            )
```

### 6. User Commands

```python
# Godfather commands for schedule management

# Create schedule
"Schedule a daily check-in at 9am asking about my priorities"
→ Creates TIME_OF_DAY schedule

"Every Monday at 10am, remind me to review weekly goals"
→ Creates DAY_OF_WEEK schedule

"Every 3 days, check in on Project Alpha progress"
→ Creates INTERVAL schedule

"On the 1st of each month, prompt me for expense review"
→ Creates DAY_OF_MONTH schedule

# Manage schedules
"/schedules" or "Show my schedules"
→ Lists all active schedules

"/schedule pause <id>" or "Pause schedule 1"
→ Temporarily disable schedule

"/schedule delete <id>" or "Delete schedule 2"
→ Remove schedule

"/schedule edit <id>" or "Edit schedule 1"
→ Modify schedule parameters
```

### 7. Natural Language Schedule Creation

```python
# src/handlers/schedule_parser.py

class ScheduleParser:
    """Parse natural language into schedule configuration."""
    
    def parse_schedule_request(self, text: str) -> dict:
        """Use AI to parse schedule from natural language."""
        
        prompt = f"""
        Parse this schedule request into structured data:
        "{text}"
        
        Extract:
        - trigger_type: cron|time_of_day|interval|day_of_week|day_of_month
        - trigger_config: appropriate configuration
        - message_template or prompt_for_ai
        - name: short descriptive name
        
        Return JSON.
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "system",
                "content": "You are a schedule parsing assistant."
            }, {
                "role": "user",
                "content": prompt
            }],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)

# Example usage:
# Input: "Every Monday at 9am, ask me about weekly goals"
# Output:
{
    "trigger_type": "day_of_week",
    "trigger_config": {
        "days": ["monday"],
        "time": "09:00"
    },
    "message_type": "static",
    "message_template": "Good morning! How are your weekly goals looking?",
    "name": "Monday Weekly Goals Check"
}
```

## Storage Schema

```json
// state/schedules.json
{
  "schedule-uuid-1": {
    "schedule_id": "schedule-uuid-1",
    "user_id": "972501234567@c.us",
    "chat_id": "972501234567@c.us",
    "name": "Daily Morning Briefing",
    "description": "Morning check-in with priorities",
    "trigger_type": "time_of_day",
    "trigger_config": {
      "time": "08:00",
      "days": ["mon", "tue", "wed", "thu", "fri"]
    },
    "message_type": "dynamic",
    "prompt_for_ai": "Generate a friendly morning greeting and ask about today's priorities. Include any upcoming deadlines from memory.",
    "enabled": true,
    "created_at": "2026-01-17T10:00:00Z",
    "last_triggered": "2026-01-17T08:00:00Z",
    "trigger_count": 5,
    "timezone": "Asia/Jerusalem"
  },
  "schedule-uuid-2": {
    "schedule_id": "schedule-uuid-2",
    "user_id": "972501234567@c.us",
    "chat_id": "972501234567@c.us",
    "name": "Friday Week Review",
    "trigger_type": "day_of_week",
    "trigger_config": {
      "days": ["friday"],
      "time": "17:00"
    },
    "message_type": "static",
    "message_template": "🎉 Week complete! What were your biggest wins this week?",
    "enabled": true,
    "created_at": "2026-01-15T12:00:00Z",
    "last_triggered": "2026-01-17T17:00:00Z",
    "trigger_count": 2
  }
}
```

## Integration with Main Bot

```python
# denidin.py - Add scheduler thread

import threading

def main():
    # ... existing initialization ...
    
    # Initialize scheduler
    schedule_manager = ScheduleManager()
    chat_scheduler = ChatScheduler(
        schedule_manager=schedule_manager,
        whatsapp_handler=whatsapp_handler,
        ai_handler=ai_handler,
        memory_manager=memory_manager
    )
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(
        target=chat_scheduler.start,
        daemon=True
    )
    scheduler_thread.start()
    logger.info("Chat scheduler started in background")
    
    # ... existing bot loop ...
```

## Configuration

```json
{
  "scheduler": {
    "enabled": true,
    "timezone": "Asia/Jerusalem",
    "check_interval_seconds": 30,
    "max_schedules_per_user": 20,
    "allow_roles": ["admin", "godfather"]
  }
}
```

## Implementation Plan

### Phase 1: Core Scheduler
- [ ] Implement ScheduledChat model
- [ ] Create ScheduleManager (JSON storage)
- [ ] Implement basic ChatScheduler
- [ ] Add time-of-day triggers
- [ ] Test with simple static messages

### Phase 2: Advanced Triggers
- [ ] Add cron support (croniter)
- [ ] Implement interval triggers
- [ ] Add day-of-week triggers
- [ ] Add day-of-month triggers
- [ ] Test all trigger types

### Phase 3: Dynamic Messages
- [ ] AI-generated messages
- [ ] Memory integration
- [ ] Template variables
- [ ] Context-aware messaging

### Phase 4: Natural Language Interface
- [ ] Schedule parsing from NL
- [ ] Schedule management commands
- [ ] User-friendly schedule creation
- [ ] Edit/pause/delete schedules

### Phase 5: Advanced Features
- [ ] Event-based triggers
- [ ] Condition-based triggers
- [ ] Schedule analytics
- [ ] Smart scheduling suggestions

## Dependencies

```python
# requirements.txt additions
schedule>=1.2.0           # Simple scheduler
croniter>=2.0.0          # Cron parsing
pytz>=2024.1             # Timezone handling
APScheduler>=3.10.0      # Alternative: advanced scheduler
```

## Example Scenarios

### Scenario 1: Daily Morning Routine
```
Godfather: "Every weekday at 8am, send me a morning briefing"

System creates:
- Time-of-day trigger (8:00 AM, Mon-Fri)
- Dynamic message using AI
- Pulls from memory: calendar, tasks, overdue items

Next morning at 8:00 AM:
Bot → "☀️ Good morning! It's Monday, January 20, 2026.

Today's priorities from our discussions:
• Follow up with Sarah on proposal
• Review Q1 budget
• Team meeting at 2pm

3 invoices need attention. Want details?"
```

### Scenario 2: Project Check-in
```
Godfather: "Every 3 days, ask me about Project Alpha progress"

System creates:
- Interval trigger (72 hours)
- Context-aware message

3 days later:
Bot → "Hey! It's been 3 days since we discussed Project Alpha. 
Last time you mentioned the deadline is March 1st and you were 
working on the API integration. How's it going?"
```

### Scenario 3: Weekly Review
```
Godfather: "Every Friday at 5pm, help me review the week"

Friday at 5pm:
Bot → "🎉 Week complete!

This week you:
• Created 8 invoices (₪42,500 total)
• Had conversations about Project Alpha, Client ABC
• Marked 5 tasks as done

What were your biggest wins this week? 
What needs attention next week?"
```

### Scenario 4: Event-Driven
```
System configuration:
- Event: Invoice overdue by 7 days
- Check: Every 6 hours

When invoice becomes 7 days overdue:
Bot → "⚠️ Invoice #INV-001 to Tech Corp (₪5,000) is now 7 days overdue. 
Would you like me to send a payment reminder?"
```

## Success Metrics

- ✅ Schedules trigger reliably within 1 minute of target time
- ✅ Dynamic messages are contextual and useful
- ✅ Godfather can create schedules via natural language
- ✅ No missed triggers due to system failures
- ✅ Schedule management is intuitive
- ✅ 90%+ test coverage for scheduler

## Security & Privacy

- **Authorization**: Only Godfather and Admin can create schedules
- **Rate Limiting**: Max 20 active schedules per user
- **Validation**: Sanitize cron expressions and intervals
- **Logging**: Audit trail of all schedule executions
- **Timezone**: Respect user's timezone for all triggers

## Testing Strategy

### Unit Tests
- Schedule parsing and creation
- Trigger time calculations
- Cron expression validation
- Message generation

### Integration Tests
- End-to-end schedule execution
- Multi-trigger coordination
- Dynamic message with memory
- Error handling

### Manual Tests
1. Create daily schedule, verify next-day trigger
2. Create interval schedule, verify periodic triggers
3. Test natural language schedule creation
4. Pause/resume/delete schedules
5. Dynamic message quality

## Future Enhancements

- **Smart Scheduling**: AI suggests optimal times based on user patterns
- **Adaptive Frequency**: Adjust frequency based on user engagement
- **Schedule Templates**: Pre-built schedule templates for common use cases
- **Multi-User Schedules**: Coordinate schedules across team members
- **Rich Messages**: Support buttons, quick replies in scheduled messages
- **Analytics**: Show schedule effectiveness, engagement rates
- **Snooze**: "Snooze this check-in for 2 hours"
- **Conditional Chains**: "If I say yes, then ask follow-up X"

## Dependencies on Other Features

- **Required**: Feature 004 (MCP WhatsApp) - Send proactive messages
- **Required**: Feature 006 (RBAC) - Godfather role verification
- **Enhanced by**: Feature 007 (Memory) - Context-aware messages
- **Enhanced by**: Feature 005 (Green Receipt) - Invoice event triggers

---

**Next Steps**:
1. Review and approve spec
2. Create feature branch `008-scheduled-proactive-chats`
3. Implement Phase 1 (Core Scheduler)
4. Test with simple time-of-day triggers
5. Iterate to dynamic AI-generated messages
