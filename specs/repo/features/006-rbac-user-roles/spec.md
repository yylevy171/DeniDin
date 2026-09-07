# Feature Spec: Role-Based Access Control (RBAC)

**Feature ID**: 006-rbac-user-roles  
**Priority**: P0 (Critical)  
**Status**: Planning  
**Created**: January 17, 2026

## Problem Statement

Currently, DeniDin treats all WhatsApp users equally - anyone can interact with the AI without restrictions. As the system grows with powerful MCP integrations (WhatsApp messaging, Green Receipt invoicing), we need to control who can do what.

**Security Risks Without RBAC:**
- Any WhatsApp user could send messages to other contacts via MCP
- Anyone could create invoices in your Morning account
- No audit trail of who performed actions
- No way to limit AI usage per user
- Cannot restrict sensitive operations

## User Roles

### Role 1: ADMIN (You - The Programmer)
**Permissions**: Full system access, everything allowed

**Capabilities:**
- ✅ Full AI interaction (unlimited)
- ✅ Send WhatsApp messages via MCP to anyone
- ✅ Create/manage invoices in Green Receipt
- ✅ Add context sources and data
- ✅ Manage user roles (promote/demote users)
- ✅ Access system logs and analytics
- ✅ Configure bot settings
- ✅ Execute admin commands
- ✅ Override any restrictions

**Admin Commands:**
- `/adduser <phone> <role>` - Add new user with role
- `/setrole <phone> <role>` - Change user role
- `/listusers` - List all users and their roles
- `/removeuser <phone>` - Remove user access
- `/logs <user>` - View user activity logs
- `/stats` - System statistics
- `/config <setting> <value>` - Update configuration
- `/shutdown` - Stop the bot
- `/broadcast <message>` - Send to all users

### Role 2: GODFATHER (Trusted Power User)
**Permissions**: Most operations allowed, some restrictions

**Capabilities:**
- ✅ Full AI interaction (high limits)
- ✅ Send WhatsApp messages via MCP (to approved contacts only)
- ✅ Create/manage invoices in Green Receipt (full access)
- ✅ Add context sources (documents, links, data)
- ✅ Upload media files (images, PDFs)
- ✅ Create chat sessions with history
- ✅ Access personal analytics
- ❌ Cannot manage user roles (no admin commands)
- ❌ Cannot access system configuration
- ❌ Cannot view other users' data

**Use Case**: Business partner, trusted colleague, executive assistant

**Restrictions:**
- WhatsApp contacts whitelist (can only message pre-approved contacts)
- Daily AI token limit (e.g., 100K tokens/day)
- Invoice creation limit (e.g., 50 invoices/month)
- Cannot execute admin commands

### Role 3: CLIENT (Read-Only User)
**Permissions**: Limited interaction, mostly read-only

**Capabilities:**
- ✅ Basic AI interaction (with limits)
- ✅ Ask questions, get information
- ✅ View their own invoice status (if applicable)
- ❌ Cannot send WhatsApp messages via MCP
- ❌ Cannot create/manage invoices
- ❌ Cannot add context sources
- ❌ Cannot upload media files
- ❌ Cannot access MCP tools
- ❌ Very limited AI usage

**Use Case**: Customers, external contacts, basic users

**Restrictions:**
- Daily AI token limit (e.g., 5K tokens/day)
- Rate limiting (max 10 messages/hour)
- Cannot use any MCP tools
- Responses are informational only
- No access to sensitive data

### Role 4: BLOCKED (Blacklisted)
**Permissions**: None - completely blocked

**Capabilities:**
- ❌ All access denied
- Bot ignores messages from blocked users
- Optional auto-reply: "You do not have access to this bot"

**Use Case**: Spam, abusive users, revoked access

## Technical Design

### 1. Data Model

```python
# src/models/user.py

from enum import Enum
from datetime import datetime
from typing import Optional, List

class UserRole(str, Enum):
    ADMIN = "admin"
    GODFATHER = "godfather"
    CLIENT = "client"
    BLOCKED = "blocked"

class User:
    user_id: str                    # WhatsApp phone number (e.g., "1234567890@c.us")
    phone_number: str               # Cleaned number: "1234567890"
    name: str                       # Display name
    role: UserRole                  # User role
    created_at: datetime
    last_active: datetime
    
    # Usage tracking
    daily_tokens_used: int          # Reset daily
    daily_messages_sent: int        # Reset daily
    total_tokens_used: int          # Lifetime
    total_messages_sent: int        # Lifetime
    
    # Permissions
    whitelisted_contacts: List[str] # For GODFATHER - who they can message
    custom_permissions: dict        # Override defaults
    
    # Metadata
    notes: str                      # Admin notes about user
    created_by: str                 # Admin who added them
    last_role_change: datetime
```

### 2. User Database

**Option 1: JSON File (MVP)**
```json
// users.json
{
  "users": {
    "972501234567@c.us": {
      "phone_number": "972501234567",
      "name": "Admin Yaron",
      "role": "admin",
      "created_at": "2026-01-17T10:00:00Z",
      "last_active": "2026-01-17T22:00:00Z",
      "daily_tokens_used": 0,
      "total_tokens_used": 125000,
      "notes": "System administrator"
    },
    "972509876543@c.us": {
      "phone_number": "972509876543",
      "name": "John Partner",
      "role": "godfather",
      "created_at": "2026-01-15T08:00:00Z",
      "whitelisted_contacts": [
        "972501111111@c.us",
        "972502222222@c.us"
      ],
      "daily_tokens_used": 2500,
      "notes": "Business partner - full invoice access"
    },
    "972505555555@c.us": {
      "phone_number": "972505555555",
      "name": "Client Sarah",
      "role": "client",
      "created_at": "2026-01-16T12:00:00Z",
      "daily_tokens_used": 150,
      "notes": "Customer - limited access"
    }
  },
  "config": {
    "default_role": "client",
    "auto_add_unknown_users": false
  }
}
```

**Option 2: Database (Production)**
```sql
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    role VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    daily_tokens_used INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    whitelisted_contacts JSON,
    custom_permissions JSON,
    notes TEXT
);
```

### 3. Permission System

```python
# src/utils/permissions.py

class Permission(str, Enum):
    AI_INTERACT = "ai_interact"
    SEND_WHATSAPP = "send_whatsapp"
    CREATE_INVOICE = "create_invoice"
    MANAGE_INVOICE = "manage_invoice"
    UPLOAD_MEDIA = "upload_media"
    ADD_CONTEXT = "add_context"
    MANAGE_USERS = "manage_users"
    VIEW_LOGS = "view_logs"
    SYSTEM_CONFIG = "system_config"
    USE_MCP_TOOLS = "use_mcp_tools"

# Permission matrix
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.AI_INTERACT,
        Permission.SEND_WHATSAPP,
        Permission.CREATE_INVOICE,
        Permission.MANAGE_INVOICE,
        Permission.UPLOAD_MEDIA,
        Permission.ADD_CONTEXT,
        Permission.MANAGE_USERS,
        Permission.VIEW_LOGS,
        Permission.SYSTEM_CONFIG,
        Permission.USE_MCP_TOOLS,
    ],
    UserRole.GODFATHER: [
        Permission.AI_INTERACT,
        Permission.SEND_WHATSAPP,      # With restrictions
        Permission.CREATE_INVOICE,
        Permission.MANAGE_INVOICE,
        Permission.UPLOAD_MEDIA,
        Permission.ADD_CONTEXT,
        Permission.USE_MCP_TOOLS,       # Limited tools
    ],
    UserRole.CLIENT: [
        Permission.AI_INTERACT,         # With strict limits
    ],
    UserRole.BLOCKED: []
}

# Usage limits
ROLE_LIMITS = {
    UserRole.ADMIN: {
        "daily_token_limit": None,      # Unlimited
        "daily_message_limit": None,
        "hourly_message_limit": None,
        "invoice_monthly_limit": None,
    },
    UserRole.GODFATHER: {
        "daily_token_limit": 100000,
        "daily_message_limit": 200,
        "hourly_message_limit": 50,
        "invoice_monthly_limit": 50,
    },
    UserRole.CLIENT: {
        "daily_token_limit": 5000,
        "daily_message_limit": 20,
        "hourly_message_limit": 10,
        "invoice_monthly_limit": 0,     # Cannot create invoices
    },
    UserRole.BLOCKED: {
        "daily_token_limit": 0,
        "daily_message_limit": 0,
        "hourly_message_limit": 0,
        "invoice_monthly_limit": 0,
    }
}

class PermissionChecker:
    def __init__(self, user_manager: UserManager):
        self.user_manager = user_manager
    
    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        user = self.user_manager.get_user(user_id)
        if not user:
            return False
        
        # Check custom permissions first
        if user.custom_permissions and permission in user.custom_permissions:
            return user.custom_permissions[permission]
        
        # Check role-based permissions
        return permission in ROLE_PERMISSIONS.get(user.role, [])
    
    def check_limit(self, user_id: str, limit_type: str) -> bool:
        """Check if user is within usage limits."""
        user = self.user_manager.get_user(user_id)
        if not user:
            return False
        
        limits = ROLE_LIMITS.get(user.role, {})
        limit = limits.get(limit_type)
        
        if limit is None:  # Unlimited
            return True
        
        # Check current usage against limit
        if limit_type == "daily_token_limit":
            return user.daily_tokens_used < limit
        elif limit_type == "daily_message_limit":
            return user.daily_messages_sent < limit
        # ... other checks
        
        return True
    
    def require_permission(self, user_id: str, permission: Permission):
        """Decorator/helper to enforce permission."""
        if not self.has_permission(user_id, permission):
            raise PermissionDeniedError(
                f"User {user_id} does not have permission: {permission}"
            )
```

### 4. User Manager

```python
# src/utils/user_manager.py

class UserManager:
    def __init__(self, storage_path: str = "state/users.json"):
        self.storage_path = storage_path
        self.users: Dict[str, User] = {}
        self.load_users()
    
    def load_users(self):
        """Load users from storage."""
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.users = {
                    uid: User(**udata) 
                    for uid, udata in data.get("users", {}).items()
                }
    
    def save_users(self):
        """Save users to storage."""
        data = {
            "users": {
                uid: user.dict() 
                for uid, user in self.users.items()
            }
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.users.get(user_id)
    
    def add_user(
        self,
        user_id: str,
        name: str,
        role: UserRole,
        created_by: str,
        notes: str = ""
    ) -> User:
        """Add new user."""
        user = User(
            user_id=user_id,
            phone_number=user_id.replace("@c.us", ""),
            name=name,
            role=role,
            created_at=datetime.now(),
            created_by=created_by,
            notes=notes
        )
        self.users[user_id] = user
        self.save_users()
        return user
    
    def update_role(
        self,
        user_id: str,
        new_role: UserRole,
        admin_id: str
    ):
        """Change user role."""
        user = self.get_user(user_id)
        if user:
            user.role = new_role
            user.last_role_change = datetime.now()
            user.notes += f"\nRole changed to {new_role} by {admin_id} on {datetime.now()}"
            self.save_users()
    
    def remove_user(self, user_id: str):
        """Remove user from system."""
        if user_id in self.users:
            del self.users[user_id]
            self.save_users()
    
    def increment_usage(self, user_id: str, tokens: int = 0):
        """Track user usage."""
        user = self.get_user(user_id)
        if user:
            user.daily_tokens_used += tokens
            user.total_tokens_used += tokens
            user.daily_messages_sent += 1
            user.total_messages_sent += 1
            user.last_active = datetime.now()
            self.save_users()
    
    def reset_daily_limits(self):
        """Reset daily counters (run via cron at midnight)."""
        for user in self.users.values():
            user.daily_tokens_used = 0
            user.daily_messages_sent = 0
        self.save_users()
    
    def get_users_by_role(self, role: UserRole) -> List[User]:
        """Get all users with specific role."""
        return [u for u in self.users.values() if u.role == role]
```

### 5. Integration with Message Flow

```python
# denidin.py - Modified message handling

async def handle_message(notification: dict):
    """Process incoming WhatsApp message with RBAC."""
    
    # Extract sender info
    sender_id = notification['senderData']['chatId']  # "1234567890@c.us"
    message_text = notification['messageData']['textMessageData']['textMessage']
    
    # 1. Get or auto-register user
    user = user_manager.get_user(sender_id)
    if not user:
        # Unknown user - check if auto-add is enabled
        if config.auto_add_unknown_users:
            user = user_manager.add_user(
                user_id=sender_id,
                name=notification['senderData'].get('senderName', 'Unknown'),
                role=UserRole.CLIENT,  # Default role
                created_by="system",
                notes="Auto-added unknown user"
            )
            logger.info(f"Auto-added new user: {sender_id} as CLIENT")
        else:
            logger.warning(f"Message from unknown user {sender_id} - ignoring")
            return
    
    # 2. Check if blocked
    if user.role == UserRole.BLOCKED:
        logger.info(f"Ignored message from blocked user: {sender_id}")
        whatsapp_handler.send_message(
            sender_id,
            "You do not have access to this bot."
        )
        return
    
    # 3. Check rate limits
    if not permission_checker.check_limit(user.user_id, "hourly_message_limit"):
        logger.warning(f"User {sender_id} exceeded hourly message limit")
        whatsapp_handler.send_message(
            sender_id,
            "⚠️ You have exceeded your hourly message limit. Please try again later."
        )
        return
    
    # 4. Handle admin commands (ADMIN only)
    if message_text.startswith('/'):
        if user.role != UserRole.ADMIN:
            whatsapp_handler.send_message(
                sender_id,
                "❌ You do not have permission to execute commands."
            )
            return
        
        # Process admin command
        handle_admin_command(user, message_text)
        return
    
    # 5. Check AI interaction permission
    if not permission_checker.has_permission(user.user_id, Permission.AI_INTERACT):
        whatsapp_handler.send_message(
            sender_id,
            "❌ You do not have permission to interact with the AI."
        )
        return
    
    # 6. Check token limits
    if not permission_checker.check_limit(user.user_id, "daily_token_limit"):
        whatsapp_handler.send_message(
            sender_id,
            "⚠️ You have reached your daily AI usage limit. Resets at midnight."
        )
        return
    
    # 7. Process AI request
    ai_response = ai_handler.get_response(
        user_message=message_text,
        user_role=user.role,  # Pass role for context
        user_id=user.user_id
    )
    
    # 8. Track usage
    user_manager.increment_usage(
        user.user_id,
        tokens=ai_response.tokens_used
    )
    
    # 9. Send response
    whatsapp_handler.send_message(sender_id, ai_response.content)
```

### 6. MCP Tool Authorization

```python
# MCP server tool call authorization

@app.call_tool()
async def call_tool(name: str, arguments: dict, context: dict) -> list[TextContent]:
    # Extract user from context (passed from WhatsApp bot)
    user_id = context.get("user_id")
    
    if name == "send_whatsapp_message":
        # Check permission
        if not permission_checker.has_permission(user_id, Permission.SEND_WHATSAPP):
            return [TextContent(
                type="text",
                text="❌ You do not have permission to send WhatsApp messages."
            )]
        
        # For GODFATHER - check whitelist
        user = user_manager.get_user(user_id)
        if user.role == UserRole.GODFATHER:
            recipient = arguments["recipient"]
            resolved_id = contact_resolver.resolve(recipient)
            
            if resolved_id not in user.whitelisted_contacts:
                return [TextContent(
                    type="text",
                    text=f"❌ You are not authorized to send messages to {recipient}."
                )]
        
        # Proceed with sending...
        
    elif name == "create_invoice":
        # Check permission
        if not permission_checker.has_permission(user_id, Permission.CREATE_INVOICE):
            return [TextContent(
                type="text",
                text="❌ You do not have permission to create invoices."
            )]
        
        # Check monthly limit
        # ... proceed
```

### 7. Admin Commands

```python
# src/handlers/admin_handler.py

class AdminCommandHandler:
    def __init__(self, user_manager: UserManager):
        self.user_manager = user_manager
    
    def handle_command(self, admin_user: User, command: str) -> str:
        """Process admin command and return response."""
        
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "/adduser":
            # /adduser 972501234567 godfather John Partner
            phone = parts[1]
            role = UserRole(parts[2])
            name = " ".join(parts[3:])
            user_id = f"{phone}@c.us"
            
            user = self.user_manager.add_user(
                user_id=user_id,
                name=name,
                role=role,
                created_by=admin_user.user_id
            )
            return f"✅ User added: {name} ({phone}) as {role.value}"
        
        elif cmd == "/setrole":
            # /setrole 972501234567 client
            phone = parts[1]
            new_role = UserRole(parts[2])
            user_id = f"{phone}@c.us"
            
            self.user_manager.update_role(user_id, new_role, admin_user.user_id)
            return f"✅ User {phone} role changed to {new_role.value}"
        
        elif cmd == "/listusers":
            users = self.user_manager.users.values()
            lines = ["📋 System Users:\n"]
            for user in users:
                lines.append(
                    f"• {user.name} ({user.phone_number})\n"
                    f"  Role: {user.role.value}\n"
                    f"  Tokens: {user.daily_tokens_used:,} today / {user.total_tokens_used:,} total\n"
                )
            return "\n".join(lines)
        
        elif cmd == "/removeuser":
            # /removeuser 972501234567
            phone = parts[1]
            user_id = f"{phone}@c.us"
            self.user_manager.remove_user(user_id)
            return f"✅ User {phone} removed from system"
        
        elif cmd == "/stats":
            total_users = len(self.user_manager.users)
            admins = len(self.user_manager.get_users_by_role(UserRole.ADMIN))
            godfathers = len(self.user_manager.get_users_by_role(UserRole.GODFATHER))
            clients = len(self.user_manager.get_users_by_role(UserRole.CLIENT))
            blocked = len(self.user_manager.get_users_by_role(UserRole.BLOCKED))
            
            total_tokens = sum(u.total_tokens_used for u in self.user_manager.users.values())
            
            return f"""📊 System Statistics:
Total Users: {total_users}
  - Admins: {admins}
  - Godfathers: {godfathers}
  - Clients: {clients}
  - Blocked: {blocked}

Total Tokens Used: {total_tokens:,}
"""
        
        else:
            return f"❌ Unknown command: {cmd}"
```

## Configuration

```json
// config.json
{
  "rbac": {
    "enabled": true,
    "auto_add_unknown_users": false,
    "default_role": "client",
    "user_storage": "state/users.json"
  },
  "admin_users": [
    "972501234567@c.us"  // Bootstrap admin
  ]
}
```

## Implementation Plan

### Phase 1: Core RBAC
- [ ] Create User and Permission models
- [ ] Implement UserManager (JSON storage)
- [ ] Create PermissionChecker
- [ ] Add role checking to message handler
- [ ] Write unit tests for permissions

### Phase 2: Admin Commands
- [ ] Implement AdminCommandHandler
- [ ] Add user management commands
- [ ] Add statistics and logging commands
- [ ] Test admin operations

### Phase 3: Usage Limits
- [ ] Implement token tracking
- [ ] Add rate limiting per role
- [ ] Create daily reset mechanism
- [ ] Add limit exceeded messages

### Phase 4: MCP Integration
- [ ] Add authorization to MCP tools
- [ ] Implement whitelist for GODFATHER
- [ ] Add permission checks to all MCP operations
- [ ] Test cross-integration

### Phase 5: Auditing
- [ ] Create audit log for all operations
- [ ] Track who did what and when
- [ ] Add admin log viewing commands
- [ ] Implement log rotation

## Security Considerations

- **Bootstrap Admin**: First user must be defined in config
- **Role Escalation**: Only ADMIN can change roles
- **Audit Trail**: Log all role changes and sensitive operations
- **Token Tracking**: Prevent abuse via usage limits
- **Whitelist Enforcement**: GODFATHER cannot bypass contact restrictions
- **Command Validation**: Sanitize all admin command inputs

## Testing Strategy

### Unit Tests
- Permission checking logic
- Role-based access control
- Usage limit enforcement
- Admin command parsing

### Integration Tests
- End-to-end message flow with different roles
- Admin command execution
- MCP tool authorization
- Limit exceeded scenarios

### Manual Testing
1. Test as ADMIN (full access)
2. Test as GODFATHER (limited access)
3. Test as CLIENT (read-only)
4. Test as BLOCKED (no access)
5. Test limit exceeded scenarios
6. Test admin commands

## Success Metrics

- ✅ Proper access control for all roles
- ✅ Usage limits enforced correctly
- ✅ Admin commands work reliably
- ✅ No unauthorized access to sensitive operations
- ✅ Audit trail complete
- ✅ 90%+ test coverage for RBAC

## Future Enhancements

- **Custom Roles**: Define roles beyond the 4 default
- **Time-Based Permissions**: Grant temporary access
- **Group Permissions**: Role inheritance for WhatsApp groups
- **API Keys**: Generate API keys for programmatic access
- **2FA**: Two-factor auth for admin operations
- **Approval Workflow**: Require approval for sensitive ops
- **Session Management**: Timeout inactive sessions
- **Permission Delegation**: ADMIN can delegate specific permissions

---

**Next Steps**:
1. Review and approve spec
2. Create feature branch `006-rbac-user-roles`
3. Implement Phase 1 (Core RBAC)
4. Add bootstrap admin configuration
5. Test thoroughly with different roles
