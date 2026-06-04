# MCP Server Selection - Smart Task Escalation Engine

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Frontend | React + Next.js | 18 / 14 (App Router) |
| Backend | Node.js + Express.js | 20 / 4.x |
| Database | PostgreSQL | 15 |
| Testing | Jest + Playwright | 29.x / 1.40+ |
| Cloud Infrastructure | AWS (ECS, RDS, S3) | - |
| Email Service | SendGrid | v3 API |

## Selected MCP Servers

### 1. PostgreSQL Schema MCP

**Purpose:** Provides AI coding agents with live, real-time access to the actual database schema, including table structures, column types, foreign key relationships, indexes, and constraints.

**Benefit to AI Coding Agents:**
- **Prevents column name errors:** Agent reads exact column names from live schema (e.g., `escalated_to` not `escalatedTo`)
- **Ensures correct JOIN syntax:** Agent knows foreign key relationships and generates accurate JOIN statements
- **Validates data types:** Agent uses correct PostgreSQL types (UUID, JSONB, TIMESTAMP) without hallucination
- **Generates accurate migrations:** Agent creates schema-aware migration scripts that won't conflict with existing structure
- **Avoids query failures:** Agent prevents querying non-existent columns or using wrong table aliases

**Example Without MCP:**
```sql
-- AI might hallucinate incorrect column names
SELECT escalation_id, escalatedTo, created_date 
FROM escalation 
WHERE status = 'active';
```

**Example With MCP:**
```sql
-- AI uses exact schema
SELECT id, escalated_to, created_at 
FROM escalations 
WHERE status = 'pending';
```

**Justification:** Database schema is a frequent source of AI hallucinations. Without live schema access, agents guess column names based on training data, leading to runtime SQL errors that only surface during execution. This MCP eliminates that entire category of errors.

---

### 2. Next.js 14 MCP

**Purpose:** Provides current Next.js 14 App Router documentation, including file-based routing conventions, server actions, middleware patterns, and layout composition rules.

**Benefit to AI Coding Agents:**
- **Uses latest App Router patterns:** Agent generates `app/` directory structure instead of deprecated `pages/` router
- **Correct server actions syntax:** Agent knows `'use server'` directive placement and async form handling patterns
- **Accurate routing conventions:** Agent creates route.ts files, understands dynamic segments `[id]`, and loading.tsx conventions
- **Proper middleware usage:** Agent implements middleware in correct location with updated API
- **Avoids deprecated APIs:** Agent doesn't use `getServerSideProps` or other Pages Router legacy patterns

**Example Without MCP:**
```javascript
// Agent generates deprecated Pages Router pattern
// pages/escalations/[id].js
export async function getServerSideProps(context) {
  // Old pattern
}
```

**Example With MCP:**
```javascript
// Agent generates correct App Router pattern
// app/escalations/[id]/page.tsx
export default async function EscalationDetailPage({ params }) {
  // Modern App Router pattern
}
```

**Justification:** Next.js 14 introduced major breaking changes with App Router. Training data for most LLMs predates this, so without MCP, agents default to deprecated patterns that won't work in Next.js 14 projects.

---

### 3. Node.js 20 MCP

**Purpose:** Provides current Node.js 20 API reference, including modern async patterns, import/export syntax, built-in modules, and deprecated API warnings.

**Benefit to AI Coding Agents:**
- **Prevents deprecated method usage:** Agent knows `fs.promises` is standard, not callback-based `fs` methods
- **Correct async/await patterns:** Agent uses modern error handling with try/catch instead of outdated callback patterns
- **Accurate import syntax:** Agent uses ESM imports (`import`/`export`) correctly with file extensions where required
- **Built-in module awareness:** Agent knows which APIs are built-in (e.g., `node:crypto`, `node:fs`) vs third-party
- **Performance best practices:** Agent applies Node.js 20 performance optimizations (e.g., `--experimental-network-imports`)

**Example Without MCP:**
```javascript
// Agent might use deprecated callback pattern
const fs = require('fs');
fs.readFile('file.txt', (err, data) => {
  if (err) throw err;
  console.log(data);
});
```

**Example With MCP:**
```javascript
// Agent uses modern async pattern
import { readFile } from 'node:fs/promises';
try {
  const data = await readFile('file.txt', 'utf8');
  console.log(data);
} catch (error) {
  console.error('Failed to read file:', error);
}
```

**Justification:** Node.js evolves rapidly. Callback-based APIs have been deprecated in favor of promises, but older training data doesn't reflect this. MCP ensures agents generate idiomatic modern Node.js code.

---

### 4. Express.js MCP

**Purpose:** Provides Express framework documentation covering middleware ordering, route handlers, error handling middleware, request/response APIs, and router patterns.

**Benefit to AI Coding Agents:**
- **Correct middleware ordering:** Agent knows error handlers come last, `express.json()` before route handlers
- **Proper error handling:** Agent implements 4-parameter error middleware correctly
- **Accurate route patterns:** Agent uses correct path parameter syntax (`:id`) and query param access
- **Request validation:** Agent knows built-in methods like `req.body`, `req.params`, `req.query`
- **Router organization:** Agent creates modular routers with correct mounting patterns

**Example Without MCP:**
```javascript
// Agent might put error handler in wrong position
app.use(errorHandler); // Wrong: error handler before routes
app.use('/api', routes);
```

**Example With MCP:**
```javascript
// Agent places error handler correctly
app.use('/api', routes);
app.use(errorHandler); // Correct: error handler after all routes
```

**Justification:** Express middleware ordering is critical to correct behavior, but not intuitive. Without framework-specific context, agents frequently generate middleware chains that fail silently or throw runtime errors.

---

### 5. Jest MCP

**Purpose:** Provides Jest testing framework APIs including test structure, matchers, mocking patterns, async testing, and coverage configuration.

**Benefit to AI Coding Agents:**
- **Correct test structure:** Agent uses `describe`, `test`, `beforeEach` with proper nesting
- **Accurate matcher syntax:** Agent uses correct matchers (`toEqual`, `toBe`, `toThrow`) without inventing non-existent ones
- **Proper mocking:** Agent uses `jest.fn()`, `jest.mock()`, `jest.spyOn()` correctly
- **Async test handling:** Agent knows to use `async/await` or return promises in async tests
- **Coverage configuration:** Agent sets up coverage thresholds and exclusions accurately

**Example Without MCP:**
```javascript
// Agent might invent non-existent matchers
expect(result).toBeSuccessful(); // Not a real Jest matcher
```

**Example With MCP:**
```javascript
// Agent uses actual Jest matchers
expect(result.success).toBe(true);
expect(result.data).toEqual(expectedData);
```

**Justification:** Test frameworks have large API surfaces with specific syntax. Without MCP, agents frequently hallucinate matcher names or use incorrect assertion patterns that cause test failures.

---

### 6. Playwright MCP

**Purpose:** Provides Playwright browser automation APIs including selectors, wait strategies, assertions, page interactions, and browser context management.

**Benefit to AI Coding Agents:**
- **Current selector syntax:** Agent uses modern `getByRole`, `getByText` over deprecated `querySelector`
- **Proper wait strategies:** Agent uses `waitForSelector`, `waitForLoadState` correctly to avoid flaky tests
- **Accurate assertions:** Agent uses Playwright's assertion library (`expect(page).toHaveTitle()`)
- **Browser context handling:** Agent manages isolated contexts for parallel test execution
- **Network interception:** Agent uses `page.route()` for API mocking in E2E tests

**Example Without MCP:**
```javascript
// Agent uses outdated selector strategy
const button = await page.$('#submit-button'); // Old CSS selector
await button.click();
```

**Example With MCP:**
```javascript
// Agent uses modern accessible selector
await page.getByRole('button', { name: 'Submit' }).click();
await expect(page).toHaveURL(/\/success/);
```

**Justification:** Playwright has evolved significantly in recent versions, deprecating CSS selectors in favor of accessible selectors. Without MCP, agents generate brittle E2E tests using outdated patterns.

---

### 7. SendGrid MCP

**Purpose:** Provides SendGrid API v3 documentation covering email sending, template usage, list management, webhook handling, and error codes.

**Benefit to AI Coding Agents:**
- **Correct API structure:** Agent uses v3 API format (not v2), which has different request structure
- **Template parameter handling:** Agent knows how to pass dynamic template data correctly
- **Error code interpretation:** Agent handles SendGrid-specific errors (rate limits, invalid email, bounces)
- **Webhook signature verification:** Agent implements webhook security correctly
- **Batch sending patterns:** Agent uses batch API for multiple recipients efficiently

**Example Without MCP:**
```javascript
// Agent might use v2 API structure (deprecated)
const msg = {
  to: 'user@example.com',
  from: 'noreply@company.com',
  subject: 'Alert',
  text: 'Message'
};
```

**Example With MCP:**
```javascript
// Agent uses v3 API structure
const msg = {
  personalizations: [{
    to: [{ email: 'user@example.com' }],
    dynamic_template_data: { taskTitle, dueDate }
  }],
  from: { email: 'noreply@company.com' },
  template_id: 'd-abc123'
};
```

**Justification:** SendGrid's API has undergone major version changes. Using wrong API version results in 400 errors at runtime. MCP ensures agent generates code compatible with current SendGrid infrastructure.

---

### 8. AWS SDK MCP

**Purpose:** Provides AWS SDK v3 documentation for service clients (S3, ECS, Secrets Manager), credential handling, error types, and configuration patterns.

**Benefit to AI Coding Agents:**
- **V3 client syntax:** Agent uses new modular client structure (`@aws-sdk/client-s3`) not old v2 SDK
- **Correct credential chains:** Agent implements credential resolution order correctly
- **Service-specific APIs:** Agent uses accurate method names for each AWS service
- **Error handling:** Agent catches and handles AWS-specific error types (`NoSuchKey`, `AccessDenied`)
- **Configuration patterns:** Agent sets region, credentials, retry policies correctly

**Example Without MCP:**
```javascript
// Agent uses deprecated v2 SDK
const AWS = require('aws-sdk');
const s3 = new AWS.S3();
```

**Example With MCP:**
```javascript
// Agent uses v3 SDK (current)
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
const client = new S3Client({ region: 'us-east-1' });
```

**Justification:** AWS SDK v3 is a complete rewrite with different import paths, client initialization, and command patterns. Without MCP, agents generate v2 code that won't work in projects using v3.

---

## MCP Selection Rationale Summary

| Selection Criterion | Rationale |
|---------------------|-----------|
| **Stack Coverage** | All 8 servers directly map to technologies in our stack. No generic/unused servers included. |
| **Version Specificity** | Each server provides version-specific documentation (Next.js 14, Node 20, AWS SDK v3) preventing deprecated code generation. |
| **High Error Risk Areas** | Selected servers target areas where AI hallucination is frequent: database schemas, framework APIs, external service integration. |
| **Mandatory Activation** | All 8 servers are non-negotiable. Omitting any single server increases defect risk significantly. |
| **Developer Productivity** | Developers spend less time fixing AI-generated errors when agents have live context. Estimated 40% reduction in debugging time. |

## Validation Checklist

Before any development session, the engineering lead must verify:
- [ ] All 8 MCP servers are active and responsive
- [ ] Server versions match stack versions (Next.js 14, not 13; Jest 29, not 28)
- [ ] Network connectivity to MCP server endpoints is stable
- [ ] Authentication credentials for MCP servers (if required) are configured

Any session beginning without full MCP activation is a process violation per SDLR Phase 6 standards.

## Alternative Approaches Considered and Rejected

**Option 1: Rely on AI training data without MCP**
- **Rejected:** Training data is months/years out of date. For rapidly evolving frameworks (Next.js, AWS SDK), this guarantees deprecated code generation.

**Option 2: Use only database and framework MCPs (skip external services)**
- **Rejected:** SendGrid and AWS SDK integration errors are expensive to debug. External service MCPs pay for themselves in first integration.

**Option 3: Manually document APIs in PLAN.md**
- **Rejected:** Manual documentation becomes stale immediately and is never comprehensive. MCP servers auto-update with latest API changes.

---

## Conclusion

All 8 selected MCP servers are justified by direct stack alignment, high error prevention value, and adherence to SDLR Phase 6 requirements. The configuration is minimal (only necessary servers) while providing maximum AI coding accuracy.
