# Smart Task Escalation Engine - Architecture Design

## System Overview

The Smart Task Escalation Engine is a proactive task management capability that automatically detects overdue tasks, escalates them through appropriate hierarchies, and ensures accountability through role-based notifications. The system operates as a modular component within the existing HRMS platform, designed for seamless integration with the current task management infrastructure.

**Business Objective:** Reduce task completion delays by 60% through automated escalation and manager visibility.

**Core Capabilities:**
- Real-time overdue task detection
- Configurable escalation rules
- Multi-level escalation workflows
- Role-based notification routing
- Comprehensive audit trail

## Modular Monolith Structure

The Smart Task Escalation Engine follows SDLR's modular monolith architecture pattern, organized into four primary modules within a single deployable application:

```
Smart Task Escalation Engine
│
├── Escalation Detection Module
│   ├── Task Monitoring Service
│   ├── Overdue Detection Logic
│   └── Escalation Rule Engine
│
├── Escalation Workflow Module
│   ├── Escalation Orchestrator
│   ├── Hierarchy Resolution Service
│   └── Escalation State Manager
│
├── Notification Module
│   ├── Notification Dispatcher
│   ├── Template Manager
│   └── Delivery Channel Router
│
└── Audit & Permissions Module
    ├── Audit Logger
    ├── Permission Validator
    └── Access Control Manager
```

**Module Boundaries:**
- Each module owns its business logic and validation rules
- Modules communicate through internal APIs with clear contracts
- Shared database with module-specific schema ownership
- No circular dependencies between modules

## Data Flow

### Primary User Journey: Task Escalation Flow

```
Task Becomes Overdue
    ↓
Detection Service (Scheduled Job)
    ↓
Evaluate Escalation Rules
    ↓
Resolve Manager Hierarchy
    ↓
Create Escalation Record
    ↓
Trigger Notification
    ↓
Update Task Status
    ↓
Log Audit Entry
```

### Data Flow Detail

1. **Detection Phase**
   - Scheduled job queries tasks table for overdue items
   - Applies business rules (grace periods, task priority, previous escalations)
   - Filters based on task status and ownership

2. **Escalation Creation**
   - Validates task eligibility
   - Resolves reporting hierarchy from employee records
   - Creates escalation entity with status tracking
   - Links escalation to original task

3. **Notification Phase**
   - Retrieves manager contact details
   - Selects notification template based on escalation level
   - Dispatches via configured channel (email/in-app)
   - Records notification delivery status

4. **Audit Phase**
   - Captures complete escalation event
   - Records all state transitions
   - Maintains immutable audit log

## Frontend ↔ Backend Interaction

### Frontend Responsibilities
- Display escalation dashboard for managers
- Show escalation history timeline
- Provide manual escalation trigger interface
- Render notification preferences UI

### Backend API Contracts

**Escalation Management APIs**
- `POST /api/escalations` - Create manual escalation
- `GET /api/escalations/:taskId` - Fetch escalation history
- `PUT /api/escalations/:id/status` - Update escalation status
- `GET /api/escalations/pending` - List pending escalations

**Notification APIs**
- `POST /api/notifications/trigger` - Manual notification trigger
- `GET /api/notifications/preferences` - User notification settings

### Authentication Flow
- All API endpoints require JWT-based authentication
- Role-based access control enforced at API gateway level
- Manager role required for escalation management endpoints
- Employee role can view own task escalations only

## Authentication Approach

**Selected Strategy:** JWT-based authentication with role-based authorization

**Rationale:**
- Stateless token approach scales horizontally
- Existing HRMS platform uses JWT infrastructure
- Role claims embedded in token payload reduce database lookups
- Refresh token mechanism already implemented

**Authorization Model:**
```
Roles:
- Employee: View own tasks and escalations
- Manager: View team escalations, trigger manual escalations
- Admin: Full system access, configure escalation rules
- System: Automated background jobs
```

**Token Structure:**
```json
{
  "userId": "EMP-12345",
  "role": "Manager",
  "permissions": ["view:escalations", "trigger:escalation"],
  "exp": 1719000000
}
```

## Database Entities

### Core Tables

**1. escalations**
```sql
CREATE TABLE escalations (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES tasks(id),
    escalated_from UUID REFERENCES employees(id),
    escalated_to UUID NOT NULL REFERENCES employees(id),
    escalation_level INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL, -- pending, acknowledged, resolved, cancelled
    escalation_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_escalated_to (escalated_to),
    INDEX idx_status (status)
);
```

**2. escalation_rules**
```sql
CREATE TABLE escalation_rules (
    id UUID PRIMARY KEY,
    task_type VARCHAR(100),
    overdue_threshold_hours INTEGER NOT NULL,
    escalation_level INTEGER NOT NULL,
    target_role VARCHAR(50) NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**3. escalation_audit_log**
```sql
CREATE TABLE escalation_audit_log (
    id UUID PRIMARY KEY,
    escalation_id UUID NOT NULL REFERENCES escalations(id),
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB,
    triggered_by UUID REFERENCES employees(id),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_escalation_id (escalation_id),
    INDEX idx_timestamp (timestamp)
);
```

**4. notification_queue**
```sql
CREATE TABLE notification_queue (
    id UUID PRIMARY KEY,
    escalation_id UUID NOT NULL REFERENCES escalations(id),
    recipient_id UUID NOT NULL REFERENCES employees(id),
    notification_type VARCHAR(50) NOT NULL, -- email, in_app, sms
    template_id VARCHAR(100),
    payload JSONB,
    status VARCHAR(50) NOT NULL, -- queued, sent, failed, retrying
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);
```

### Relationships
- `escalations.task_id` → `tasks.id` (existing table)
- `escalations.escalated_to` → `employees.id` (existing table)
- `escalation_audit_log.escalation_id` → `escalations.id`
- `notification_queue.escalation_id` → `escalations.id`

## External Integrations

### SendGrid (Email Notifications)
**Purpose:** Reliable transactional email delivery for escalation notifications

**Integration Pattern:**
- Async job queue for email dispatch
- Retry mechanism for failed sends (3 attempts with exponential backoff)
- Template management via SendGrid dashboard
- Webhook receiver for delivery status updates

**Configuration Required:**
- API Key stored in AWS Secrets Manager
- Verified sender domain
- Template IDs for each escalation level

### Existing HRMS APIs
**Purpose:** Access employee hierarchy and organizational structure

**Endpoints Used:**
- `GET /api/employees/:id/manager` - Resolve reporting manager
- `GET /api/employees/:id/profile` - Retrieve contact details
- `GET /api/organizational-hierarchy/:employeeId` - Multi-level hierarchy resolution

**Authentication:** Service-to-service JWT with system role

## Build vs Buy Decisions

### Decision Matrix

| Capability | Decision | Rationale |
|------------|----------|-----------|
| Email Delivery | **BUY** (SendGrid) | Infrastructure-heavy, requires deliverability management, IP reputation, bounce handling. SendGrid pricing ($15/month for 40k emails) is negligible compared to engineering effort. |
| Task Detection | **BUILD** | Core business logic, requires deep integration with existing task schema, custom business rules. Can be built in one sprint using agentic tools. |
| Hierarchy Resolution | **BUILD** | Organizational hierarchy rules are company-specific, integration already exists with HRMS employee service. Extension work, not net-new infrastructure. |
| Notification Queue | **BUILD** | Simple async job queue using PostgreSQL advisory locks and background workers. No need for external message broker at current scale (<10k users). |
| Audit Logging | **BUILD** | Compliance requirement necessitates full control over audit data retention and structure. PostgreSQL JSONB storage sufficient for current needs. |

### Third-Party Services

**SendGrid** (Email Delivery)
- **Cost:** $15/month for 40,000 emails
- **Justification:** Proven deliverability, compliance with CAN-SPAM, GDPR email handling, webhook infrastructure
- **Alternative Considered:** AWS SES - rejected due to complex bounce/complaint handling requirements

**No Other External Dependencies Required**
- Notification infrastructure kept simple
- Database capabilities sufficient for queuing
- Existing authentication system reused

## Non-Functional Requirements

### Performance Targets
- Overdue detection job completes in <30 seconds for 50,000 tasks
- Escalation creation API response time: P95 < 500ms
- Notification dispatch: <2 minutes from escalation creation
- Audit log writes: async, non-blocking

### Scalability Considerations
- Detection job uses cursor-based pagination for large task datasets
- Notification dispatch uses batch processing (100 notifications per batch)
- Database indexes on escalation status and task_id for query performance
- Connection pooling configured for 50 concurrent connections

### Security Requirements
- All API endpoints protected with JWT authentication
- Role-based access control enforced on every request
- Sensitive audit data encrypted at rest (database-level encryption)
- No PII in notification templates (use placeholders only)
- Rate limiting: 100 requests per minute per user

## Open Questions

| Question | Owner | Target Resolution |
|----------|-------|-------------------|
| What is the maximum escalation depth? (e.g., 3 levels up hierarchy) | Product Team | Before PLAN.md finalization |
| Should escalations auto-resolve when task is completed? | Product Team | ARB Review |
| Grace period for first-time overdue tasks? | Product Team | Before development |
| SMS notification support required in MVP? | Product Team | Defer to Sprint N+1 if not critical |

## Architecture Compliance

This design adheres to SDLR principles:
- ✅ Modular monolith with clear boundaries
- ✅ PostgreSQL as central database
- ✅ Build-vs-buy framework applied
- ✅ External services limited to infrastructure-heavy capabilities
- ✅ Authentication reuses existing HRMS JWT infrastructure
- ✅ API-first design with clear contracts
- ✅ Audit logging for compliance

## ARB Review Readiness

This architecture document is ready for Architecture Review Board validation. All mandatory sections are complete, external dependencies justified, and planning files prepared for development initialization.
