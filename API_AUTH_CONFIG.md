# CLIVIO — Auth & Configuration API
**Version:** 1.0 | **Base URL:** `https://clivio.onrender.com/api` | **Format:** JSON

---

## Token Overview

All protected endpoints require a `Bearer` token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

| Token | Lifetime | Storage |
|-------|----------|---------|
| Access | 15 minutes | Memory / React state |
| Refresh | 7 days | HttpOnly cookie or secure storage |

**JWT payload:**
```json
{
  "user_id": 1,
  "role": "super_admin",
  "clinic_id": 1,
  "name": "Super Admin",
  "exp": 1714000000
}
```

**Token expiry flow:**
```
Request with expired access token
        ↓
API returns 401
        ↓
POST /api/auth/refresh  →  new access + refresh tokens
        ↓
Retry original request
        ↓
If refresh also fails → redirect to /login
```

---

## Authentication Endpoints

### POST `/api/auth/login`
Login with email and password.
Rate-limited to **5 attempts per 15 minutes per IP**.

**Request:**
```json
{
  "username": "admin@clivio.com",
  "password": "admin123"
}
```

**Response `200 OK`:**
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>",
  "user": {
    "id": 1,
    "name": "Super Admin",
    "email": "admin@clivio.com",
    "role": "super_admin",
    "clinic_id": 1,
    "clinic_name": "Clivio Dermatology"
  }
}
```

**Response `401 Unauthorized`:**
```json
{ "error": "Invalid email or password." }
```

**Response `403 Forbidden`:**
```json
{ "error": "This account has been deactivated." }
```

**Response `429 Too Many Requests`:**
```json
{ "error": "Too many failed attempts. Try again in 15 minutes." }
```

---

### POST `/api/auth/refresh`
Get a new access token using the refresh token.
The old refresh token is **blacklisted** and a new one is issued — store the new one.

**Request:**
```json
{ "refresh": "<jwt_refresh_token>" }
```

**Response `200 OK`:**
```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

**Response `401 Unauthorized`:**
```json
{ "error": "Token is invalid or expired." }
```
> If this happens → clear stored tokens and redirect to `/login`.

---

### POST `/api/auth/logout`
Blacklist the refresh token. Requires `Authorization` header.

**Request:**
```json
{ "refresh": "<jwt_refresh_token>" }
```

**Response `200 OK`:**
```json
{ "message": "Logged out successfully." }
```

---

### POST `/api/auth/forgot-password`
Send a password reset link to the user's email.
Always returns `200` to prevent email enumeration.

**Request:**
```json
{ "email": "doctor@clivio.com" }
```

**Response `200 OK`:**
```json
{ "message": "If that email exists, a reset link has been sent." }
```

---

### POST `/api/auth/reset-password`
Consume the reset token from the email link and set a new password.

**Request:**
```json
{
  "token": "<reset_token_from_email>",
  "password": "newpassword123"
}
```

**Response `200 OK`:**
```json
{ "message": "Password updated successfully." }
```

**Response `400 Bad Request`:**
```json
{ "error": "Invalid or expired token." }
```

---

## Configuration Endpoints

> `GET` is **public** — no token required.
> `POST` / `PATCH` require a **Super Admin** token.
> **Content-Type:** `multipart/form-data` — images are uploaded as files, not base64.
> ⚠️ Do **NOT** set `Content-Type` manually — the browser/fetch sets it automatically with the correct boundary.

---

### GET `/api/configuration`
Retrieve clinic branding and settings.
**No authentication required** — call this on app load to style the login page.

**Response `200 OK`:**
```json
{
  "id": 1,
  "clinic_name": "Clivio Dermatology",
  "logo": "/media/attachments/logo.png",
  "logo_url": "https://clivio.onrender.com/media/attachments/logo.png",
  "hero_image": "/media/attachments/hero.jpg",
  "hero_image_url": "https://clivio.onrender.com/media/attachments/hero.jpg",
  "slogan": "Your skin, our care",
  "sub_slogan": "Expert dermatology since 2015",
  "footer_info": "© 2026 Clivio Dermatology. All rights reserved.",
  "linkedin_url": "https://linkedin.com/company/clivio",
  "instagram_url": "https://instagram.com/clivio",
  "facebook_url": "https://facebook.com/clivio",
  "whatsapp_url": "https://wa.me/201000000000",
  "primary_color": "#1ABC9C",
  "secondary_color": "#0F172A",
  "updated_at": "2026-04-13T12:00:00Z"
}
```

> Use `logo_url` and `hero_image_url` directly in `<img src>` — they are absolute URLs.

**Response `404 Not Found`:**
```json
{ "detail": "No configuration found." }
```

---

### POST `/api/configuration`
Create configuration for the first time. **Super Admin only.**

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `clinic_name` | string | ✅ |
| `logo` | file (image) | ✅ |
| `hero_image` | file (image) | ✅ |
| `primary_color` | hex string e.g. `#1ABC9C` | ✅ |
| `secondary_color` | hex string | ❌ |
| `slogan` | string | ❌ |
| `sub_slogan` | string | ❌ |
| `footer_info` | string | ❌ |
| `linkedin_url` | URL | ❌ |
| `instagram_url` | URL | ❌ |
| `facebook_url` | URL | ❌ |
| `whatsapp_url` | URL | ❌ |

**JavaScript example:**
```javascript
const formData = new FormData();
formData.append('clinic_name', 'Clivio Dermatology');
formData.append('primary_color', '#1ABC9C');
formData.append('logo', logoFile);        // File from <input type="file">
formData.append('hero_image', heroFile);  // File from <input type="file">

const res = await fetch('https://clivio.onrender.com/api/configuration', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${accessToken}` },
  body: formData,
  // ⚠️ No Content-Type header — let the browser set it
});
```

**Response `201 Created`:** Full configuration object (same shape as GET).

**Response `409 Conflict`:**
```json
{ "error": "Configuration already exists. Use PATCH to update." }
```

---

### PATCH `/api/configuration`
Update existing configuration. **Super Admin only.**
All fields are optional — only send what you want to change.

**Content-Type:** `multipart/form-data`

**JavaScript example:**
```javascript
const formData = new FormData();
formData.append('primary_color', '#e11d48');  // only changed fields
formData.append('logo', newLogoFile);          // only if updating logo

const res = await fetch('https://clivio.onrender.com/api/configuration', {
  method: 'PATCH',
  headers: { 'Authorization': `Bearer ${accessToken}` },
  body: formData,
});
```

**Response `200 OK`:** Updated configuration object (same shape as GET).

**Response `404 Not Found`:**
```json
{ "error": "No configuration found. Use POST to create it first." }
```

---

## Branch Endpoints

> All branch endpoints require a **Super Admin** token.
> **Content-Type:** `application/json`

---

### GET `/api/branches?page=1`
List branches for the clinic. Paginated — **10 per page**.

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `page` | integer | Page number (default: 1) |

**Response `200 OK`:**
```json
{
  "total": 25,
  "page_size": 10,
  "page": 1,
  "next": "https://clivio.onrender.com/api/branches?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Cairo Branch",
      "address": "123 Nile St, Maadi",
      "phone": "+20100000000",
      "is_active": true
    }
  ]
}
```

---

### POST `/api/branches`
Create a new branch. **Super Admin only.**

| Field | Type | Required |
|-------|------|----------|
| `name` | string | ✅ |
| `phone` | string | ✅ |
| `address` | string | ✅ |
| `is_active` | boolean | ❌ (default: true) |

**Response `201 Created`:** Full branch object.

**Response `400 Bad Request`:**
```json
{ "name": ["A branch with this name already exists."] }
```

---

### GET `/api/branches/:id`
Retrieve a single branch.

**Response `200 OK`:** Full branch object.

---

### PATCH `/api/branches/:id`
Update a branch. All fields optional.

**Response `200 OK`:** Updated branch object.

---

### PATCH `/api/branches/:id/status`
Activate or deactivate a branch.

**Request:**
```json
{ "is_active": false }
```

**Response `200 OK`:**
```json
{ "id": 1, "is_active": false }
```

---

### GET `/api/branches/:id/users`
List all staff assigned to a branch.

**Response `200 OK`:**
```json
[
  {
    "id": 1,
    "name": "Dr. Ahmed",
    "email": "ahmed@clivio.com",
    "role": "doctor",
    "role_display": "Doctor",
    "phone": "+20100000000",
    "specialty": "Dermatologist",
    "role_title": "Senior Doctor",
    "is_active": true,
    "assigned_at": "2026-04-13T12:00:00Z"
  }
]
```

---

## Error Reference

| Status | Meaning |
|--------|---------|
| `400` | Validation error — check field-level messages |
| `401` | Missing, expired, or invalid token |
| `403` | Authenticated but wrong role |
| `404` | Resource not found |
| `409` | Conflict — already exists |
| `429` | Rate limit exceeded |

---

*CLIVIO — Confidential. Internal use only.*
