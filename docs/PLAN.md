# Smart Task Escalation Engine - Implementation Plan

## Active MCP Servers

The following MCP servers must be activated before any development session begins. These provide live engineering context to AI coding agents and prevent hallucinated APIs, deprecated syntax, and incorrect integration patterns.

| MCP Server | Purpose | Benefit |
|------------|---------|---------|
| **PostgreSQL Schema MCP** | Live database schema access | Prevents column name errors, ensures correct JOIN syntax, validates foreign key relationships, generates accurate migration scripts |
| **Next.js 14 MCP** | Latest Next.js App Router documentation | Ensures correct file-based routing, server actions syntax, middleware patterns, and layout conventions |
| **Node.js 20 MCP** | Current Node.js API reference | Prevents use of deprecated methods, ensures correct async/await patterns, validates import syntax |
| **Express.js MCP** | Express framework documentation | Correct middleware ordering, route handler patterns, error handling conventions |
| **Jest MCP** | Jest testing framework APIs | Accurate test structure, mock syntax, assertion methods, coverage configuration |
| **Playwright MCP** | Playwright automation APIs | Current selector syntax, wait strategies, assertion methods, browser context handling |
| **SendGrid MCP** | SendGrid API documentation | Correct email sending patterns, template usage, webhook handling, error codes |
| **AWS SDK MCP** | AWS SDK v3 documentation | Correct service client usage, credential handling, CloudWatch logging patterns |

**Validation Before Each Session:**
- Confirm all 8 MCP servers are active and responsive
- If any server is unavailable, resolve connectivity before proceeding
- Note any MCP configuration changes in STATUS.md

## Implementation Tasks

### Phase 1: Database Foundation

- [ ] **Task 1.1: Create Database Migration Scripts**
  - Create migration for `escalations` table with proper indexes
  - Create migration for `escalation_rules` table
  - Create migration for `escalation_audit_log` table with JSONB event storage
  - Create migration for `notification_queue` table
  - **Acceptance Criteria:**
    - All foreign key constraints defined
    - Indexes on high-query columns (task_id, status, escalated_to)
    - Timestamp columns with DEFAULT NOW()
    - Migration runs successfully on clean database
    - Rollback script included for each migration

- [ ] **Task 1.2: Create Database Seed Data**
  - Seed sample escalation rules (3 rule types: standard, urgent, critical)
  - Seed test employee records with manager relationships
  - Seed sample task data for testing detection logic
  - **Acceptance Criteria:**
    - Seed data covers all task types
    - Manager hierarchy includes 3 levels for testing escalation depth
    - Test data includes edge cases (tasks without managers, circular reporting)

- [ ] **Task 1.3: Database Connection Pool Configuration**
  - Configure PostgreSQL connection pool (min: 5, max: 50)
  - Add connection retry logic with exponential backoff
  - Implement graceful shutdown handling
  - **Acceptance Criteria:**
    - Connection pool reuses connections efficiently
    - Failed connections trigger retry with 1s, 2s, 4s backoff
    - Application exits cleanly without hanging connections

### Phase 2: Escalation Detection Module

- [ ] **Task 2.1: Task Monitoring Service**
  - Implement query logic to fetch overdue tasks
  - Add pagination for large task datasets (100 tasks per batch)
  - Filter tasks based on status (exclude completed, cancelled)
  - **Acceptance Criteria:**
    - Query executes in <5 seconds for 50,000 tasks
    - Cursor-based pagination implemented correctly
    - Only tasks with status 'in_progress' or 'assigned' are retrieved

- [ ] **Task 2.2: Overdue Detection Logic**
  - Implement business rules for overdue calculation
  - Apply grace period logic (configurable per task type)
  - Check for existing escalations to prevent duplicates
  - **Acceptance Criteria:**
    - Overdue threshold calculated correctly (due_date + grace_period < now)
    - Tasks with active escalations are skipped
    - Weekend/holiday handling implemented (business days only)

- [ ] **Task 2.3: Escalation Rule Engine**
  - Implement rule matching logic (task type → escalation rule)
  - Support multiple escalation levels (L1, L2, L3)
  - Add rule priority handling (most specific rule wins)
  - **Acceptance Criteria:**
    - Rule engine selects correct rule for each task type
    - Default rule applies when no specific match found
    - Inactive rules are ignored

- [ ] **Task 2.4: Scheduled Job Configuration**
  - Configure cron job to run detection every 15 minutes
  - Add job locking to prevent concurrent execution
  - Implement error recovery and job retry logic
  - **Acceptance Criteria:**
    - Job runs on schedule: `*/15 * * * *`
    - Only one instance runs at a time (advisory lock used)
    - Job failure logged to CloudWatch with stack trace

### Phase 3: Escalation Workflow Module

- [ ] **Task 3.1: Hierarchy Resolution Service**
  - Implement manager lookup via HRMS API integration
  - Support multi-level escalation (resolve L1, L2, L3 managers)
  - Handle edge cases (employee without manager, circular reporting)
  - **Acceptance Criteria:**
    - Integration with `/api/employees/:id/manager` endpoint working
    - Circular reporting structure detected and logged as error
    - Fallback to HR admin when manager chain ends

- [ ] **Task 3.2: Escalation Creation API**
  - Implement `POST /api/escalations` endpoint
  - Validate task exists and is eligible for escalation
  - Create escalation record with all required fields
  - **Acceptance Criteria:**
    - API returns 201 Created with escalation object
    - Validation rejects invalid task IDs (404 Not Found)
    - Duplicate escalation attempts return 409 Conflict
    - Role authorization enforced (manager role required)

- [ ] **Task 3.3: Escalation State Manager**
  - Implement state transitions (pending → acknowledged → resolved)
  - Add validation for invalid state changes
  - Update timestamps on state changes (acknowledged_at, resolved_at)
  - **Acceptance Criteria:**
    - State machine enforces valid transitions only
    - Attempting invalid transition returns 400 Bad Request
    - All state changes logged to audit table

- [ ] **Task 3.4: Escalation History API**
  - Implement `GET /api/escalations/:taskId` endpoint
  - Return escalation history ordered by creation date (newest first)
  - Include manager details and escalation level in response
  - **Acceptance Criteria:**
    - Endpoint returns array of escalation objects
    - Response includes manager name, email, escalation_level
    - Empty array returned for tasks with no escalations
    - Authorization enforced (own tasks or team tasks only)

### Phase 4: Notification Module

- [ ] **Task 4.1: Notification Queue Writer**
  - Implement queue insertion logic on escalation creation
  - Store notification payload as JSONB (task details, manager info)
  - Set initial status as 'queued'
  - **Acceptance Criteria:**
    - Queue record created for every new escalation
    - Payload includes all template variables (taskTitle, dueDate, employeeName)
    - Queue insertion is transactional with escalation creation

- [ ] **Task 4.2: SendGrid Integration**
  - Configure SendGrid API client with retry logic
  - Implement email sending function with template support
  - Handle SendGrid errors (invalid email, rate limits, API failures)
  - **Acceptance Criteria:**
    - Email sent successfully via SendGrid API
    - Template ID correctly passed to SendGrid
    - SendGrid API key loaded from AWS Secrets Manager
    - 3 retry attempts with 5s, 10s, 20s backoff on failure

- [ ] **Task 4.3: Notification Dispatcher Worker**
  - Implement background worker to process notification queue
  - Batch process 100 notifications per execution
  - Update notification status (sent, failed) after dispatch
  - **Acceptance Criteria:**
    - Worker runs every 2 minutes via cron
    - Only 'queued' and 'retrying' notifications processed
    - Failed notifications marked 'failed' after 3 attempts
    - Sent notifications marked 'sent' with timestamp

- [ ] **Task 4.4: Notification Template Manager**
  - Create email templates for each escalation level (L1, L2, L3)
  - Support variable substitution (task title, employee name, due date)
  - Add plain text fallback for email clients
  - **Acceptance Criteria:**
    - Templates uploaded to SendGrid dashboard
    - Template IDs configured in environment variables
    - Variable substitution tested with sample data

- [ ] **Task 4.5: Manual Notification Trigger API**
  - Implement `POST /api/notifications/trigger` endpoint
  - Allow managers to manually resend notifications
  - Validate escalation exists and requester has permission
  - **Acceptance Criteria:**
    - Endpoint queues notification for immediate dispatch
    - Authorization enforced (manager role required)
    - Rate limiting applied (max 10 manual triggers per hour per user)

### Phase 5: Audit & Permissions Module

- [ ] **Task 5.1: Audit Logger Service**
  - Implement audit log writer for all escalation events
  - Store event data as JSONB (flexible schema for different events)
  - Include triggered_by user ID in every audit entry
  - **Acceptance Criteria:**
    - Audit log entry created for: escalation_created, escalation_acknowledged, escalation_resolved, notification_sent
    - Event data includes before/after state for updates
    - Audit writes are async and never block main workflow

- [ ] **Task 5.2: Permission Validator Middleware**
  - Implement role-based authorization middleware
  - Check JWT token claims for required permissions
  - Support resource-level authorization (own tasks vs team tasks)
  - **Acceptance Criteria:**
    - Unauthorized requests return 403 Forbidden with clear message
    - Manager role can access team escalations
    - Employee role limited to own task escalations
    - Admin role has full access

- [ ] **Task 5.3: Audit Query API**
  - Implement `GET /api/escalations/:id/audit` endpoint
  - Return complete audit trail for an escalation
  - Filter audit events by type if query param provided
  - **Acceptance Criteria:**
    - Endpoint returns chronologically ordered audit events
    - Response includes triggered_by user details (name, email)
    - Optional filter: `/audit?eventType=escalation_acknowledged`
    - Admin role required for access

### Phase 6: API Integration & Error Handling

- [ ] **Task 6.1: HRMS API Client**
  - Implement service-to-service JWT authentication
  - Create client for employee hierarchy endpoints
  - Add circuit breaker pattern for HRMS API failures
  - **Acceptance Criteria:**
    - JWT token refreshed automatically when expired
    - Circuit breaker opens after 5 consecutive failures
    - Fallback behavior defined (escalate to HR admin)

- [ ] **Task 6.2: Global Error Handler**
  - Implement centralized error handling middleware
  - Map internal errors to appropriate HTTP status codes
  - Add structured error logging (error type, stack trace, request context)
  - **Acceptance Criteria:**
    - All unhandled errors return 500 with safe error message (no stack traces in production)
    - Validation errors return 400 with field-specific messages
    - Database errors logged with query context (no sensitive data)

- [ ] **Task 6.3: Rate Limiting Middleware**
  - Implement rate limiting per user (100 requests per minute)
  - Add endpoint-specific limits (manual trigger: 10 per hour)
  - Return 429 Too Many Requests with Retry-After header
  - **Acceptance Criteria:**
    - Rate limit counters stored in-memory (production will use Redis)
    - Counter resets after time window expires
    - 429 response includes retry time in seconds

### Phase 7: Testing & Validation

- [ ] **Task 7.1: Unit Tests - Escalation Detection**
  - Test overdue calculation logic with various scenarios
  - Test rule engine with multiple rule types
  - Test duplicate escalation prevention
  - **Acceptance Criteria:**
    - 15+ test cases covering happy path and edge cases
    - Coverage > 90% for detection module
    - All tests pass deterministically

- [ ] **Task 7.2: Unit Tests - Workflow Module**
  - Test hierarchy resolution with 3-level chain
  - Test state machine transitions
  - Test escalation creation validation
  - **Acceptance Criteria:**
    - Test circular reporting detection
    - Test invalid state transition rejection
    - Coverage > 85% for workflow module

- [ ] **Task 7.3: Unit Tests - Notification Module**
  - Test SendGrid integration with mocked API
  - Test notification queue processing
  - Test retry logic on failures
  - **Acceptance Criteria:**
    - Mock SendGrid responses (success, rate limit, invalid email)
    - Test retry backoff timing
    - Coverage > 85% for notification module

- [ ] **Task 7.4: Unit Tests - Audit Module**
  - Test audit log writing for all event types
  - Test permission validation logic
  - Test audit query filtering
  - **Acceptance Criteria:**
    - Test async audit writes don't block main flow
    - Test role-based authorization rules
    - Coverage > 90% for audit module

- [ ] **Task 7.5: Integration Tests - E2E Workflow**
  - Test complete escalation flow: detection → creation → notification → audit
  - Test manual escalation trigger via API
  - Test escalation history retrieval
  - **Acceptance Criteria:**
    - Test database transactions (rollback on failure)
    - Test external API integration (HRMS, SendGrid)
    - All integration tests use test database

- [ ] **Task 7.6: Playwright E2E Tests**
  - Test escalation dashboard UI for managers
  - Test manual escalation trigger workflow
  - Test notification preference updates
  - **Acceptance Criteria:**
    - Tests run against deployed test environment
    - Browser automation covers Chrome, Firefox
    - Tests verify DOM elements and API responses

### Phase 8: Deployment Preparation

- [ ] **Task 8.1: Sentry Integration**
  - Configure Sentry SDK for error tracking
  - Add environment tags (dev, staging, production)
  - Set up release tracking with Git SHA
  - **Acceptance Criteria:**
    - Unhandled errors appear in Sentry dashboard within 30s
    - Source maps uploaded for readable stack traces
    - Performance monitoring enabled with 10% sample rate

- [ ] **Task 8.2: Docker Configuration**
  - Create Dockerfile for containerized deployment
  - Optimize image layers for faster builds
  - Add health check endpoint
  - **Acceptance Criteria:**
    - Image builds successfully: `docker build -t escalation-engine .`
    - Container runs locally: `docker run -p 3001:3001`
    - Health check endpoint responds: `GET /health`

- [ ] **Task 8.3: Infrastructure as Code**
  - Create AWS ECS task definition
  - Configure environment variables via AWS Secrets Manager
  - Define auto-scaling policy (CPU > 70%)
  - **Acceptance Criteria:**
    - ECS service deployable via CLI
    - Secrets loaded from Secrets Manager (no hardcoded values)
    - Auto-scaling triggers correctly under load

## Task Dependencies

Some tasks have dependencies and must be completed in order:

- Task 1.1 → Task 1.2 (migrations before seeds)
- Task 2.1 → Task 2.2 → Task 2.3 (detection logic builds on monitoring)
- Task 3.1 → Task 3.2 (hierarchy resolution needed for escalation creation)
- Task 4.1 → Task 4.3 (queue writer before dispatcher)
- Tasks 7.1-7.4 → Task 7.5 (unit tests before integration tests)

All other tasks can be developed in parallel by separate developers.

## Definition of Done

A task is considered complete when:
- ✅ Implementation code written and committed
- ✅ Unit tests written with >80% coverage
- ✅ Code passes linting (`npm run lint`)
- ✅ All tests pass locally (`npm test`)
- ✅ Inline documentation added for complex logic (>20 lines)
- ✅ PLAN.md checkbox marked as complete
- ✅ STATUS.md updated with completion timestamp
- ✅ Pull request created and CodeRabbit review resolved
