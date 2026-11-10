---
name: api-automation
description: "Use when automating REST, GraphQL, OpenAPI, Swagger, or Postman API tests, exploration, and schema validation."
argument-hint: "Describe the API, specification, endpoints, authentication, and test objective"
---

# API Automation

## Purpose

This skill provides specialized knowledge for API test automation, including REST and GraphQL APIs. It covers API discovery, exploration, schema validation, endpoint testing, authentication handling, and API-specific quality standards.

## When to Use

Activate this skill when:
- User mentions API, endpoint, REST, GraphQL, HTTP, or web service
- Project contains API test frameworks (RestAssured, supertest, requests, etc.)
- Test involves HTTP requests/responses
- OpenAPI/Swagger or Postman collection provided
- User explicitly requests API automation

## Prerequisites

Before using this skill:
- Project analysis completed (via `project-analysis` skill)
- API base URL or OpenAPI spec available
- Authentication requirements documented
- HTTP client available (RestAssured, axios, requests, Postman MCP)

---

## API Execution Modes

- `api-exploration` — Discover endpoints, auth flows, and schemas (requires live requests or provided spec)
- `api-execution` — Run or re-run existing API tests
- `api-debug` — Investigate failing API tests and replay traffic

---

## Tools & Sources

### Input Sources

Accept one or more of:
- **OpenAPI/Swagger file** (JSON or YAML)
- **Postman Collection** (JSON export)
- **Base URL + authentication** (for manual discovery)
- **Live API endpoint access** (for exploratory testing)

### HTTP Clients

Use appropriate client for technology stack:
- **Java**: RestAssured, OkHttp
- **JavaScript/TypeScript**: axios, supertest, Playwright API (`request` context)
- **Python**: requests, httpx
- **Postman MCP**: If available, use Postman MCP tools for API interaction

---

## API Discovery & Exploration Phase

### 1. Spec-Based Discovery (OpenAPI/Postman)

**If OpenAPI/Swagger provided:**
1. Parse spec file (JSON/YAML)
2. Extract endpoints, methods, parameters
3. Validate schemas and examples
4. Document authentication requirements (API key, Bearer token, OAuth, Basic Auth)
5. Identify request/response models
6. Note required vs optional fields

**If Postman Collection provided:**
1. Parse collection JSON
2. Extract endpoints from requests
3. Identify environment variables
4. Document authentication configuration
5. Extract example requests/responses

**Validation:**
- Verify spec is valid (use OpenAPI validator)
- Check for deprecated endpoints
- Identify required vs optional parameters
- Note data types and constraints

### 2. Live API Discovery (No Spec)

**If only base URL provided:**
1. Request endpoint list from user or documentation
2. Enumerate endpoints via guided discovery
3. For each endpoint:
   - Make exploratory request
   - Capture request/response pair
   - Document headers, status codes, body structure
   - Note authentication requirements
4. Build endpoint inventory

**Document:**
```
Endpoint: POST /api/v1/auth/login
Method: POST
Auth: None (public endpoint)
Headers:
  - Content-Type: application/json
Body:
  - username (string, required)
  - password (string, required)
Expected Response: 200 OK
Response Body:
  - token (string)
  - user (object)
    - id (integer)
    - username (string)
    - email (string)
```

### 3. Capture Real Request/Response Pairs

For each endpoint:
1. Execute real request using HTTP client
2. Capture full request:
   - Method, URL, headers, query params, body
3. Capture full response:
   - Status code, headers, body, latency
4. Document success scenarios
5. Document error scenarios (if applicable)
6. Save as fixtures for deterministic testing

**Example:**
```
Request:
POST https://api.example.com/v1/login
Headers:
  Content-Type: application/json
Body:
  {"username": "testuser", "password": "testpass"}

Response:
Status: 200 OK
Headers:
  Content-Type: application/json
Body:
  {
    "token": "eyJhbGciOiJIUzI1...",
    "user": {"id": 123, "username": "testuser"}
  }
Latency: 245ms
```

### 4. Authentication Flows

**Document authentication type:**
- **API Key**: Header or query param
- **Bearer Token**: Authorization header
- **OAuth 2.0**: Token exchange flow
- **Basic Auth**: Username/password encoded
- **Custom**: Application-specific auth

**Capture authentication flow:**
1. Initial authentication request
2. Token/key retrieval
3. Token storage/refresh strategy
4. Token usage in subsequent requests

**Example (Bearer Token):**
```
Step 1: Authenticate
POST /api/auth/login
Body: {"username": "user", "password": "pass"}
Response: {"token": "abc123"}

Step 2: Use token in subsequent requests
GET /api/users/me
Headers: Authorization: Bearer abc123
```

**Handle token refresh:**
- Document token expiration
- Implement refresh logic when needed
- Store tokens securely (environment variables)

---

## Endpoint & Schema Strategy (Locator Analogue)

### Verification Strategies Ranked by Stability

1. **OpenAPI Schema Validation**
   - Most stable, contract-driven
   - Validates response against schema
   - Catches breaking changes

2. **Response Content-Type + Field Names**
   - Validate content type (application/json)
   - Check for expected field names
   - Verify field types

3. **Status Codes**
   - Validate expected HTTP status
   - 2xx for success, 4xx for client errors, 5xx for server errors

4. **Example Payloads**
   - Compare against known good responses
   - Use for regression testing

**Best Practice:** Combine multiple strategies for robust validation.

### Schema Validation

**Use JSON Schema or OpenAPI schema:**
```java
// Java (RestAssured)
given()
  .get("/api/users/123")
.then()
  .assertThat()
  .body(matchesJsonSchemaInClasspath("user-schema.json"));
```

**Validate:**
- Required fields present
- Field types correct (string, integer, boolean, etc.)
- Array lengths within constraints
- Enum values match allowed values
- Nested object structures correct

---

## Action Execution & Validation (APIs)

### Making Requests

**Execute requests using chosen HTTP client:**

**Java (RestAssured):**
```java
Response response = given()
  .contentType("application/json")
  .header("Authorization", "Bearer " + token)
  .body(requestBody)
  .when()
  .post("/api/resource")
  .then()
  .extract().response();
```

**JavaScript (axios):**
```javascript
const response = await axios.post('/api/resource', requestBody, {
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  }
});
```

**Python (requests):**
```python
response = requests.post(
  'https://api.example.com/resource',
  json=request_body,
  headers={'Authorization': f'Bearer {token}'}
)
```

### API Success Validation (CRITICAL)

**ABSOLUTE REQUIREMENT:**
- ALL API calls MUST validate success status codes (2xx) unless explicitly testing error scenarios
- If an API returns error status (4xx, 5xx) WITHOUT user requesting error validation:
  - **STOP immediately**
  - Classify the failure
  - Re-execute with logging to capture full context
  - Analyze response body, headers, error messages
  - Attempt to fix automatically (adjust request, refresh auth, etc.)
  - If unfixable: NOTIFY USER with complete error details
- **NEVER generate tests that accept API failures as normal behavior**

**Success Criteria:**
- Status code is 2xx (200, 201, 204, etc.)
- Response body matches expected schema
- Critical fields contain expected values
- Business assertions pass (e.g., user created, order placed)

**Example Validation:**
```java
response
  .then()
  .statusCode(200)  // Must be success
  .body("status", equalTo("success"))
  .body("data.id", notNullValue())
  .time(lessThan(2000L));  // Performance assertion
```

### Validate Responses

**Check:**
1. **Status Code**: Expected HTTP status (200, 201, 400, 404, etc.)
2. **Headers**: Content-Type, Cache-Control, etc.
3. **Schema**: Response matches expected structure
4. **Critical Fields**: Key data points present and correct
5. **Business Logic**: Assertions specific to use case

**Example:**
```java
given()
  .get("/api/users/123")
.then()
  .statusCode(200)
  .contentType("application/json")
  .body("id", equalTo(123))
  .body("username", notNullValue())
  .body("email", matchesPattern("^[\\w-\\.]+@[\\w-]+\\.[a-z]{2,}$"));
```

### Handle Errors Gracefully

**When API returns error:**
1. Capture full error context
2. Check error response body for details
3. Classify error:
   - **4xx**: Client error (bad request, auth failure, not found)
   - **5xx**: Server error (internal error, service unavailable)
4. Document error for user if it's a system bug
5. Retry with exponential backoff if transient (rate limit, timeout)

---

## Code Generation & Integration (APIs)

### Generate Tests from Specs

**For each endpoint in OpenAPI/Postman:**
1. Create test method
2. Build request from spec examples
3. Execute request
4. Validate response against schema
5. Add business assertions

**No hypothetical endpoints:**
- Only generate tests for documented or discovered endpoints
- Never assume endpoint structure
- All endpoints must be validated through live requests during exploration

### Supported Tech Stacks

**Ask user first**, then fallback to defaults:

**Java + RestAssured + Cucumber (default):**
```xml
<dependency>
  <groupId>io.rest-assured</groupId>
  <artifactId>rest-assured</artifactId>
</dependency>
```

**JavaScript/TypeScript:**
- **supertest** (for Express/Node apps)
- **axios** + Jest/Mocha
- **Playwright API context** (`request` object)

**Python:**
- **requests** + pytest
- **httpx** (async support)

### Reuse Existing Patterns

- Check for existing HTTP client setup
- Reuse authentication utilities
- Follow project request/response helper patterns
- Integrate with existing test framework

---

## Execution, Classification & Auto-Fix

### Execute Generated Tests Immediately

**After code generation:**
1. Run all generated API tests
2. Capture results (pass/fail)
3. Log full request/response for failures

### On ANY API Failure, Follow This Protocol:

1. **Capture full error context:**
   - Status code, response body, headers
   - Request details (method, URL, body, headers)
   - Error message from response

2. **Re-execute with verbose logging:**
   - Enable debug mode
   - Log complete request/response cycle
   - Capture timing information

3. **Classify the failure:**
   - **`code_issue`**: Invalid request format, wrong endpoint, missing parameters, incorrect data types
   - **`system_bug`**: API returning 5xx, documented endpoint not working, data inconsistency
   - **`user_input_needed`**: Missing credentials, wrong environment, unclear expected behavior

4. **Auto-fix attempts (max 5 iterations):**
   - **Adjust request structure**: Fix JSON format, add missing required fields
   - **Fix data types**: Convert strings to integers, etc.
   - **Correct authentication**: Refresh token, fix auth header format
   - **Retry with different valid payloads**: Use alternative test data
   - **Update assertions**: Match actual API contract (if API is correct)

5. **If still failing after max attempts:**
   - STOP execution
   - Present detailed failure report to user:
     - Request sent (full details)
     - Response received (status, headers, body)
     - Attempted fixes (what was tried)
     - Root cause analysis (best guess)
   - **DO NOT deliver the script unless user explicitly acknowledges the limitation**

### Success Criteria

**All API endpoints return:**
- Expected success status codes (2xx)
- OR documented error codes if explicitly testing error scenarios (e.g., testing 404 for non-existent resource)

**Follow iterative correction until:**
- 100% functional
- OR user-acknowledged limitation

---

## Data Management & Idempotency

### Test Data Strategy

**Prefer idempotent operations:**
- GET requests (safe, repeatable)
- PUT requests with known IDs (upsert pattern)
- DELETE with verification (check if exists first)

**For creation endpoints (POST):**
- Generate unique identifiers (timestamps, UUIDs)
- Record created resource IDs
- Clean up in teardown (DELETE created resources)

**Example:**
```java
// Setup
String uniqueEmail = "test_" + System.currentTimeMillis() + "@example.com";
int userId = createUser(uniqueEmail);

// Test
// ... perform test actions

// Teardown
deleteUser(userId);
```

### Fixtures for Deterministic Testing

**Create fixtures:**
- Known request payloads
- Expected response bodies
- Mock server configurations (if needed)

**Use fixtures for:**
- Regression testing (responses shouldn't change)
- Contract testing (validate against saved contracts)
- Offline testing (mock servers with fixture responses)

---

## Reporting & Evidence

### Capture Evidence

**For each API test:**
1. **Request**: Method, URL, headers, body
2. **Response**: Status, headers, body, latency
3. **Assertions**: What was validated
4. **Result**: Pass/fail with details

### Report Format

**Support:**
- **HTML reports**: ExtentReports, Allure, custom
- **JSON reports**: Machine-readable results
- **Framework-specific**: TestNG, JUnit, Pytest reports

**Include in report:**
- Request/response excerpts
- Status codes and timing
- Schema validation results
- Links to full request/response logs (in artifacts)

### Mask Sensitive Data

**ALWAYS mask:**
- Authorization tokens
- API keys
- Passwords
- Personally identifiable information (PII)

**In reports:**
- Replace tokens with `[REDACTED]`
- Store raw evidence in secured artifact locations
- Never log full credentials

**Example:**
```
Request Headers:
  Authorization: Bearer [REDACTED]
  Content-Type: application/json
```

---

## Rate Limits & Resilience

### Handle Rate Limiting

**Detect:**
- 429 Too Many Requests status
- Retry-After header
- Rate limit error messages

**Strategy:**
- Implement exponential backoff
- Respect Retry-After header
- Reduce request frequency in tests
- Use rate limit-aware test ordering

**Example:**
```java
// Exponential backoff
int maxRetries = 3;
for (int i = 0; i < maxRetries; i++) {
  Response response = makeRequest();
  if (response.statusCode() != 429) {
    return response;
  }
  Thread.sleep((long) Math.pow(2, i) * 1000);  // 1s, 2s, 4s
}
```

### Implement Retries

**Retry for transient failures:**
- Network timeouts
- Connection refused
- 503 Service Unavailable
- 429 Rate Limit

**DO NOT retry for:**
- 400 Bad Request (fix request instead)
- 401 Unauthorized (fix auth)
- 404 Not Found (endpoint issue)
- Validation failures (fix test logic)

### Timeouts

**Set explicit timeouts:**
- Connection timeout (e.g., 5 seconds)
- Read timeout (e.g., 30 seconds)
- Total timeout (connection + read)

**Example:**
```java
given()
  .config(RestAssured.config()
    .httpClient(HttpClientConfig.httpClientConfig()
      .setParam(CoreConnectionPNames.CONNECTION_TIMEOUT, 5000)
      .setParam(CoreConnectionPNames.SO_TIMEOUT, 30000)))
  .get("/api/resource");
```

---

## API-Specific Prohibitions

### ABSOLUTE PROHIBITIONS

1. **NO TESTS EXPECTING FAILURES**: Never generate tests that expect 4xx/5xx unless explicitly testing error scenarios
2. **NO UNVALIDATED ERRORS**: Never deliver API automation where endpoints return errors without investigation
3. **NO "MIGHT WORK LATER"**: Never accept intermittent failures as valid outcomes
4. **NO MASKED FAILURES**: Never mask API failures in test reports or mark them as passed
5. **NO HYPOTHETICAL ENDPOINTS**: Require a spec or live validation before generating tests
6. **NO HARDCODED SECRETS**: Never embed API keys, tokens, passwords in test code
7. **NO ASSUMED ERROR RESPONSES**: Only test error scenarios if user explicitly requests them

---

## Integration Points

### With Other Skills

- **`project-analysis`**: Detects API test projects, identifies frameworks
- **`code-generation`**: Receives API exploration data, generates test code
- **`execution-validation`**: Executes API tests, validates results, fixes errors

### With Automation Agent

- Agent delegates API-specific exploration to this skill
- Agent uses this skill's validation criteria for API deliverables
- Agent follows this skill's error classification for API failures

---

## Quality Standards (API-Specific)

1. **Schema Validation**: Validate responses against OpenAPI/JSON schemas
2. **Status Code Validation**: Always check expected HTTP status
3. **Performance**: Document response time expectations
4. **Error Handling**: Test both success and error paths
5. **Authentication**: Securely handle credentials and tokens
6. **Data Cleanup**: Remove test data created during execution
7. **Idempotency**: Tests can run multiple times safely

---

## Examples

### Example 1: REST API Login Test

**Exploration:**
```
Endpoint: POST /api/v1/auth/login
Auth: None
Headers: Content-Type: application/json
Body:
  - username: "testuser@example.com"
  - password: "TestPass123!"
Expected Response: 200 OK
Response Body:
  - token: string
  - expiresIn: integer
```

**Generated Test (Java/RestAssured):**
```java
@Test
public void testLogin() {
  Response response = given()
    .contentType("application/json")
    .body("{\"username\": \"testuser@example.com\", \"password\": \"TestPass123!\"}")
  .when()
    .post("/api/v1/auth/login")
  .then()
    .statusCode(200)
    .contentType("application/json")
    .body("token", notNullValue())
    .body("expiresIn", greaterThan(0))
    .extract().response();
  
  // Store token for subsequent requests
  String token = response.path("token");
  assertNotNull(token);
}
```

### Example 2: OpenAPI Schema Validation

**Exploration:**
```
Endpoint: GET /api/v1/users/{id}
Auth: Bearer token
Expected Response: 200 OK, matches user-schema.json
```

**Generated Test:**
```java
@Test
public void testGetUser() {
  given()
    .header("Authorization", "Bearer " + authToken)
    .pathParam("id", 123)
  .when()
    .get("/api/v1/users/{id}")
  .then()
    .statusCode(200)
    .assertThat()
    .body(matchesJsonSchemaInClasspath("schemas/user-schema.json"))
    .body("id", equalTo(123))
    .body("email", notNullValue());
}
```

---

**End of API Automation Skill**

Use this skill whenever API automation is required. Always validate against schemas when available, and never accept API failures without investigation and classification.
