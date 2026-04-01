# Exam Paper Moderation & Tracking Portal - Architecture Blueprint

This architecture strictly adheres to the core constraint: **No files are ever uploaded, and only metadata/state transitions are tracked.**

## 1. Database Schema (PostgreSQL)

We will use PostgreSQL due to its strong relational constraints and `JSONB` support for dynamic metadata (like checklists and CO mappings).

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enum Types for strict value enforcement
CREATE TYPE user_role AS ENUM ('ADMIN', 'SETTER', 'MODERATOR', 'HOD');
CREATE TYPE paper_status AS ENUM (
    'ASSIGNED',
    'METADATA_SUBMITTED',
    'UNDER_MODERATION',
    'REVISION_REQUIRED',
    'APPROVED'
);

-- Users Table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Courses Table
CREATE TABLE courses (
    course_code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    semester INT CHECK (semester >= 1 AND semester <= 8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Allocations (The core tracking entity)
CREATE TABLE allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_code VARCHAR(50) REFERENCES courses(course_code) ON DELETE RESTRICT,
    setter_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    moderator_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    status paper_status DEFAULT 'ASSIGNED' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Ensure setter and moderator are different people
    CONSTRAINT chk_different_users CHECK (setter_id != moderator_id)
);

-- Paper Metadata (One-to-Many with Allocation to handle multiple sections)
CREATE TABLE paper_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    allocation_id UUID REFERENCES allocations(id) ON DELETE CASCADE,
    section_name VARCHAR(50) NOT NULL, -- e.g., 'Section A', 'Section B'
    total_questions INT NOT NULL CHECK (total_questions > 0),
    co_mapping_json JSONB NOT NULL, -- e.g., {"CO1": 20, "CO2": 30}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Moderation Logs (Audit trail for reviews and status changes)
CREATE TABLE moderation_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    allocation_id UUID REFERENCES allocations(id) ON DELETE CASCADE,
    action_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    action_taken paper_status NOT NULL,
    checklist_json JSONB, -- e.g., {"formatting_correct": true, "co_coverage_adequate": false}
    comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_allocations_setter ON allocations(setter_id);
CREATE INDEX idx_allocations_moderator ON allocations(moderator_id);
CREATE INDEX idx_allocations_status ON allocations(status);
```

## 2. REST API Endpoint Structure & RBAC

All endpoints require a valid JWT. The backend middleware will enforce Role-Based Access Control (RBAC).

### **Admin (Exam Cell) Endpoints**
*   `POST /api/admin/courses`
    *   **RBAC**: Admin only.
    *   **Payload**: `{ "courseCode": "CS101", "name": "Data Structures", "semester": 3 }`
*   `POST /api/admin/allocations`
    *   **RBAC**: Admin only.
    *   **Payload**: `{ "courseCode": "CS101", "setterId": "uuid", "moderatorId": "uuid", "deadline": "2023-12-01T23:59:59Z" }`

### **Paper Setter Endpoints**
*   `GET /api/setter/allocations`
    *   **RBAC**: Setter only. Returns only allocations where `setter_id == jwt.userId`.
*   `POST /api/setter/allocations/:id/metadata`
    *   **RBAC**: Setter only. Validates `allocation.setter_id == jwt.userId`.
    *   **Payload**:
        ```json
        {
          "sections": [
            { "sectionName": "A", "totalQuestions": 5, "coMapping": {"CO1": 3, "CO2": 2} },
            { "sectionName": "B", "totalQuestions": 3, "coMapping": {"CO3": 3} }
          ],
          "offlineTransferConfirmed": true
        }
        ```
    *   **Action**: Inserts into `paper_metadata` and updates Allocation status to `METADATA_SUBMITTED`.

### **Moderator Endpoints**
*   `GET /api/moderator/allocations`
    *   **RBAC**: Moderator only. Returns allocations where `moderator_id == jwt.userId`.
*   `POST /api/moderator/allocations/:id/review`
    *   **RBAC**: Moderator only.
    *   **Security Rule Enforcement**:
        1. Query allocation. If `moderator_id != jwt.userId`, return `403 Forbidden`.
        2. If `allocation.status == 'ASSIGNED'`, return `400 Bad Request` ("Setter has not submitted metadata yet").
    *   **Payload**:
        ```json
        {
          "status": "REVISION_REQUIRED", // or "APPROVED"
          "checklist": { "formatOk": true, "coCoverageOk": false },
          "comments": "Need more questions from CO3 in Section B."
        }
        ```
    *   **Action**: Inserts into `moderation_logs` and updates Allocation status.

### **HOD Endpoints**
*   `GET /api/hod/dashboard`
    *   **RBAC**: HOD only. Returns summary stats (missed deadlines, pending moderations) across all courses.
*   `GET /api/hod/allocations/:id/metadata`
    *   **RBAC**: HOD only.
    *   **Strict Security Rule**: Queries the allocation status. If `status != 'APPROVED'`, immediately return `403 Forbidden` with message *"Metadata is locked until Moderation is Approved."*

## 3. State Machine Logic Flow

To ensure data integrity, the backend should implement a state machine for the `Allocation` entity. Transitions can only happen in specific directions:

1.  **ASSIGNED**:
    *   *Trigger*: Admin creates the Allocation.
    *   *Rule*: Moderator cannot interact with it yet.
2.  **METADATA_SUBMITTED**:
    *   *Trigger*: Setter submits the metadata form AND checks the "Sent offline" boolean.
    *   *Rule*: Unlocks Moderator access.
3.  **UNDER_MODERATION**:
    *   *Trigger*: Moderator clicks "Start Review" or saves a draft checklist.
4.  **REVISION_REQUIRED**:
    *   *Trigger*: Moderator submits review with "Changes Required".
    *   *Rule*: Sends notification/email to Setter. Transitions back to `METADATA_SUBMITTED` once the Setter re-submits the form.
5.  **APPROVED**:
    *   *Trigger*: Moderator submits review with "Approved".
    *   *Rule*: **Terminal State.** Unlocks the HOD's ability to view the `paper_metadata` table for this allocation.

## 4. Security Headers & Authentication Strategy

Since this handles highly sensitive university workflows, strict security measures must be implemented.

### **Authentication Strategy (JWT via HttpOnly Cookies)**
Do not store JWTs in `localStorage`.
1.  **Access Token**: Short-lived JWT (e.g., 15 minutes) containing `{ "userId": "uuid", "role": "MODERATOR" }`.
2.  **Refresh Token**: Long-lived JWT (e.g., 7 days) stored in a strictly secure, `HttpOnly`, `SameSite=Strict` cookie.
3.  **Payload Validation**: On every request, a middleware intercepts the token, verifies the signature, extracts the `role`, and compares it against the required role for the endpoint.

### **Recommended Security Headers (Helmet.js / Nginx config)**
```http
Content-Security-Policy: default-src 'self'; api-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
Cache-Control: no-store, no-cache, must-revalidate, proxy-revalidate
```

### **Application-Level Security Enhancements**
*   **Audit Logging**: Every single POST/PUT request is written to a separate `audit_logs` table (IP address, User ID, Endpoint, Timestamp) for forensic tracking.
*   **Rate Limiting**: Apply strict rate limiting to API endpoints to prevent automated scraping or brute-forcing.
*   **UUID Iteration**: Because `AllocationID` is a UUIDv4, it is cryptographically impossible for a Setter or Moderator to guess the ID of a course they are not assigned to, inherently preventing Insecure Direct Object Reference (IDOR) attacks alongside your RBAC checks.
