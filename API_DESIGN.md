# CLIVIO — API Design Document
**Version:** 1.0 | **Base URL:** `https://clivio.onrender.com/api` | **Format:** JSON

> Auth & Configuration endpoints are documented separately in [API_AUTH_CONFIG.md](API_AUTH_CONFIG.md).
> All endpoints below require `Authorization: Bearer <access_token>` unless stated otherwise.

---

## Authentication & Configuration

> See **[API_AUTH_CONFIG.md](API_AUTH_CONFIG.md)** for all auth and configuration endpoints.

---

## CLV-SA-02 & CLV-SA-03 — Branches

### GET `/api/branches`
List all branches for the authenticated user's clinic. Available to all roles.

**Response `200 OK`:**
```json
[
  {
    "id": 1,
    "clinic": 1,
    "name": "Downtown Branch",
    "city": "Cairo",
    "area": "Zamalek",
    "address": "15 El-Tahrir St.",
    "phone": "+20 100 000 0000",
    "email": "downtown@clivio.com",
    "opening_time": "09:00:00",
    "closing_time": "21:00:00",
    "is_active": true,
    "status": "active",
    "created_at": "2026-04-13T10:00:00Z",
    "doctor_count": 3,
    "assistant_count": 2
  }
]
```

---

### POST `/api/branches`
Create a new branch. **Super Admin only.**

**Request:**
```json
{
  "name": "New Cairo Branch",
  "city": "Cairo",
  "area": "Fifth Settlement",
  "address": "90 North St., Building 7",
  "phone": "+20 100 111 2222",
  "email": "newcairo@clivio.com",
  "opening_time": "09:00",
  "closing_time": "22:00"
}
```

**Required fields:** `name`, `city`

**Response `201 Created`:**
```json
{
  "id": 2,
  "clinic": 1,
  "name": "New Cairo Branch",
  "city": "Cairo",
  "area": "Fifth Settlement",
  "address": "90 North St., Building 7",
  "phone": "+20 100 111 2222",
  "email": "newcairo@clivio.com",
  "opening_time": "09:00:00",
  "closing_time": "22:00:00",
  "is_active": true,
  "status": "active",
  "created_at": "2026-04-13T12:00:00Z",
  "doctor_count": 0,
  "assistant_count": 0
}
```

**Response `400 Bad Request` (duplicate name):**
```json
{ "name": ["A branch with this name already exists."] }
```

---

### GET `/api/branches/:id`
Retrieve a single branch with full details.

**Response `200 OK`:** Same shape as the list item above.

**Response `404 Not Found`:**
```json
{ "error": "Branch not found." }
```

---

### PATCH `/api/branches/:id`
Update branch details. **Super Admin only.** All fields optional.

**Request:**
```json
{
  "phone": "+20 100 999 8888",
  "closing_time": "23:00"
}
```

**Response `200 OK`:** Updated branch object.

---

### PATCH `/api/branches/:id/status`
Activate or deactivate a branch. **Super Admin only.**
Deactivation is **blocked** if there are upcoming confirmed appointments.

**Request:**
```json
{ "is_active": false }
```

**Response `200 OK`:**
```json
{
  "id": 1,
  "is_active": false,
  "status": "inactive"
}
```

**Response `409 Conflict`:**
```json
{
  "error": "Cannot deactivate branch. It has 3 upcoming confirmed appointment(s).",
  "upcoming_appointments": 3
}
```

---

### GET `/api/branches/:id/users`
List users assigned to this branch. Optional `role` filter.

**Query params:** `?role=doctor` | `?role=assistant`

**Response `200 OK`:**
```json
{
  "branch_id": 1,
  "branch_name": "Downtown Branch",
  "count": 2,
  "results": [
    {
      "id": 5,
      "name": "Dr. Ahmed Rabea",
      "email": "ahmed@clivio.com",
      "role": "doctor",
      "role_display": "Doctor",
      "phone": "+20 100 000 0001",
      "specialty": "Dermatologist",
      "role_title": "",
      "is_active": true,
      "assigned_at": "2026-04-13T11:00:00Z"
    }
  ]
}
```

---

## CLV-SA-04 & CLV-SA-05 — Users (Doctors & Assistants)

### GET `/api/users`
List all users in the clinic. **Super Admin only.**

**Query params:** `?role=doctor` | `?role=assistant`

**Response `200 OK`:**
```json
[
  {
    "id": 5,
    "name": "Dr. Ahmed Rabea",
    "email": "ahmed@clivio.com",
    "role": "doctor",
    "role_display": "Doctor",
    "phone": "+20 100 000 0001",
    "specialty": "Dermatologist",
    "role_title": "",
    "clinic": 1,
    "clinic_name": "Clivio Dermatology",
    "is_active": true,
    "date_joined": "2026-04-13T10:00:00Z",
    "branch_count": 2,
    "assigned_branches": [
      { "id": 1, "name": "Downtown Branch", "city": "Cairo" },
      { "id": 2, "name": "New Cairo Branch", "city": "Cairo" }
    ]
  }
]
```

---

### POST `/api/users`
Create a new doctor or assistant. **Super Admin only.**
At least one `branch_ids` entry is **required** for `doctor` and `assistant` roles.

**Request (Doctor):**
```json
{
  "name": "Dr. Sara Khalil",
  "email": "sara@clivio.com",
  "role": "doctor",
  "phone": "+20 100 222 3333",
  "specialty": "Dermatologist",
  "password": "pass1234",
  "branch_ids": [1, 2]
}
```

**Request (Assistant):**
```json
{
  "name": "Nour Hassan",
  "email": "nour@clivio.com",
  "role": "assistant",
  "phone": "+20 100 444 5555",
  "role_title": "Senior Receptionist",
  "password": "pass1234",
  "branch_ids": [1]
}
```

**Response `201 Created`:** Full user object (same shape as GET /api/users item).

**Response `400 Bad Request` (no branch):**
```json
{ "branch_ids": ["At least one branch must be assigned."] }
```

**Response `400 Bad Request` (duplicate email):**
```json
{ "email": ["This email is already registered."] }
```

---

### GET `/api/users/:id`
Retrieve a single user. **Super Admin only.**

**Response `200 OK`:** Full user object.

---

### PATCH `/api/users/:id`
Update user details. **Super Admin only.** All fields optional.

**Request:**
```json
{
  "phone": "+20 100 999 0000",
  "specialty": "Laser Dermatology"
}
```

**Response `200 OK`:** Updated user object.

---

### PATCH `/api/users/:id/status`
Activate or deactivate a user. **Super Admin only.**

**Request:**
```json
{ "is_active": false }
```

**Response `200 OK`:**
```json
{ "id": 5, "is_active": false }
```

---

### POST `/api/users/:id/branches`
Add branch assignments to an existing user (additive — does not remove existing ones). **Super Admin only.**

**Request:**
```json
{ "branch_ids": [3, 4] }
```

**Response `200 OK`:** Updated full user object with new `assigned_branches`.

---

### PATCH `/api/users/:id/branches`
Replace all branch assignments for a user. **Super Admin only.**

**Request:**
```json
{ "branch_ids": [1, 3] }
```

**Response `200 OK`:** Updated full user object.

---

## Error Reference

| Status | Meaning |
|--------|---------|
| `400` | Validation error — check field-level error messages |
| `401` | Missing or invalid/expired access token |
| `403` | Authenticated but insufficient role permissions |
| `404` | Resource not found or not in your clinic |
| `409` | Conflict — e.g. duplicate name, blocked deactivation |
| `429` | Rate limit exceeded |

---

## Role Permission Matrix

| Endpoint | super_admin | doctor | assistant |
|----------|-------------|--------|-----------|
| GET /api/configuration | ✅ public | ✅ public | ✅ public |
| POST /api/configuration | ✅ | ❌ | ❌ |
| PATCH /api/configuration | ✅ | ❌ | ❌ |
| POST /api/auth/login | ✅ | ✅ | ✅ |
| GET /api/branches | ✅ | ✅ | ✅ |
| POST /api/branches | ✅ | ❌ | ❌ |
| PATCH /api/branches/:id | ✅ | ❌ | ❌ |
| PATCH /api/branches/:id/status | ✅ | ❌ | ❌ |
| GET /api/branches/:id/users | ✅ | ✅ | ❌ |
| GET /api/users | ✅ | ❌ | ❌ |
| POST /api/users | ✅ | ❌ | ❌ |
| PATCH /api/users/:id | ✅ | ❌ | ❌ |
| POST/PATCH /api/users/:id/branches | ✅ | ❌ | ❌ |
| PATCH /api/users/:id/status | ✅ | ❌ | ❌ |

---

## Data Scoping Rule

**All queries are scoped to the authenticated user's `clinic_id`.** Cross-clinic data is never returned. Doctor and assistant endpoints additionally filter by `user_branch_assignments` — they only see data from their assigned branches.

---

## Frontend Integration Notes

1. **Store access token in memory** (not `localStorage`) — use a module-level variable or React context.
2. **Store refresh token in an HttpOnly cookie** (set by the frontend on login response).
3. **Silent token refresh:** Before any request, check if access token expires in < 60s; call `/api/auth/refresh` proactively.
4. **On 401 response:** Attempt one token refresh, retry original request. If refresh fails → redirect to `/login`.
5. **CORS:** Requests must include `credentials: 'include'` if using cookies for the refresh token.
6. **Trailing slashes:** Django does NOT use trailing slashes on API routes — use `/api/auth/login` not `/api/auth/login/`.

---

*CLIVIO — Confidential. Internal use only.*
