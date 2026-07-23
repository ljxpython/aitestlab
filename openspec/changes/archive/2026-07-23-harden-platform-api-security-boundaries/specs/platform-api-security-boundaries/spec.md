## ADDED Requirements

### Requirement: Super-administrator authority is non-delegable by operators
The platform API MUST allow only an authenticated `platform_super_admin` to grant or revoke the `platform_super_admin` role on a user or service account. Issuing a credential for a service account that carries that role MUST require the same authority.

#### Scenario: Operator creates an ordinary user
- **WHEN** a `platform_operator` creates a user without the `platform_super_admin` role
- **THEN** the platform API creates the user under the existing user-write permission

#### Scenario: Operator attempts to grant super-administrator role
- **WHEN** a `platform_operator` creates or updates a user or service account so that it gains `platform_super_admin`
- **THEN** the platform API denies the request and persists no role change

#### Scenario: Operator attempts to revoke super-administrator role
- **WHEN** a `platform_operator` updates a user or service account so that it loses `platform_super_admin`
- **THEN** the platform API denies the request and persists no role change

#### Scenario: Operator attempts to issue a super-administrator service credential
- **WHEN** a `platform_operator` requests a new API key for a service account carrying `platform_super_admin`
- **THEN** the platform API denies the request and returns no credential

#### Scenario: Super administrator manages protected role
- **WHEN** an authenticated `platform_super_admin` grants or revokes `platform_super_admin` and all existing invariants are satisfied
- **THEN** the platform API permits the mutation

### Requirement: Actor roles originate from verified authentication
The platform API MUST derive actor identity and roles only from a validated bearer token or service-account API key. Disabling mandatory authentication MUST NOT make client-supplied identity or role headers authoritative.

#### Scenario: Authentication optional without credential
- **WHEN** authentication enforcement is disabled and a request supplies identity and role headers but no valid token or API key
- **THEN** the platform API treats the actor as anonymous and protected authorization fails

#### Scenario: Verified credential replaces anonymous actor
- **WHEN** a request supplies a valid bearer token or API key
- **THEN** the platform API loads the current principal and roles from trusted persistence before authorization

### Requirement: Project permissions always require project membership
The platform API MUST require a project identifier and an allowed role for that project before granting a project-scoped permission, regardless of platform roles.

#### Scenario: Super administrator lacks project membership
- **WHEN** a `platform_super_admin` requests a project-scoped action for a project in which the actor has no allowed project role
- **THEN** the platform API denies the action for a missing project role

#### Scenario: Super administrator has project membership
- **WHEN** a `platform_super_admin` requests a project-scoped action and has an allowed role in that project
- **THEN** the platform API grants the action under the project permission mapping

#### Scenario: Project scope is absent
- **WHEN** any authenticated actor requests a project-scoped permission without `project_id`
- **THEN** the platform API rejects the request as missing project scope

### Requirement: Operation responses exclude execution identity snapshots
Public operation list, detail, watch, and mutation responses MUST NOT expose the internal actor snapshot used for asynchronous execution. Removing the field from a response MUST NOT remove it from stored execution metadata.

#### Scenario: Project member reads operation
- **WHEN** an authorized project member reads an operation whose stored metadata contains `actor_snapshot`
- **THEN** the returned metadata omits `actor_snapshot` and does not disclose the submitter's email, platform roles, or roles in other projects

#### Scenario: Worker reconstructs operation actor
- **WHEN** a worker executes an operation after public-response redaction is enabled
- **THEN** it can still reconstruct the submitted actor from stored execution metadata

### Requirement: Successful login audit identifies the actor
A successful login audit event MUST record the authenticated user's identifier and subject as the event actor without recording passwords or issued tokens.

#### Scenario: Successful login
- **WHEN** valid credentials create an authenticated session
- **THEN** the `identity.session.created` audit event contains the logged-in user's actor identifier and subject

#### Scenario: Failed login
- **WHEN** supplied credentials do not authenticate a user
- **THEN** the failed audit event does not claim an authenticated actor

### Requirement: Audit response inspection is bounded and non-stream-consuming
The audit middleware MUST capture payload data only from bounded JSON responses. It MUST NOT consume or rebuild file responses, SSE responses, generic streaming responses, unbounded JSON streams, or JSON responses above the capture limit.

#### Scenario: Bounded JSON response
- **WHEN** a JSON response declares a content length within the capture limit
- **THEN** audit resolution may inspect its object payload and the client receives the original status, headers, and body

#### Scenario: File response
- **WHEN** an endpoint returns a file response
- **THEN** audit records available response headers without iterating the file body before returning the response

#### Scenario: Streaming response
- **WHEN** an endpoint returns SSE, a generic stream, or JSON without a declared bound
- **THEN** audit does not consume the iterator and streaming behavior is preserved

#### Scenario: Oversized JSON response
- **WHEN** a JSON response declares a content length above the capture limit
- **THEN** audit skips payload capture and records the declared response length

### Requirement: User creation enforces the established password minimum
The platform API MUST reject a user creation or administrative password reset when the supplied new password is shorter than eight characters.

#### Scenario: User creation with short password
- **WHEN** an authorized caller creates a user with a password shorter than eight characters
- **THEN** request validation rejects the request before a password hash is persisted

#### Scenario: User creation with valid password length
- **WHEN** an authorized caller creates a user with a password of at least eight characters
- **THEN** password-length validation permits the request to proceed
