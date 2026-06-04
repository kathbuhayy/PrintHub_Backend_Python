# PrintHub API — Python / FastAPI

A complete Python port of the PrintHub Node.js/Express backend. All endpoints, business logic, and third-party integrations are replicated 1:1.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL via asyncpg (same Supabase DB as Node backend) |
| File Storage | Supabase S3 |
| Payments | PayMongo |
| Image Generation | FAL.ai (prod) / Pollinations.AI (free dev mode) |
| 3D Generation | Meshy API |
| Email / OTP | aiosmtplib (Gmail SMTP) |
| Validation | Pydantic v2 |

---

## Project Structure

```
PrintHub_Python/
├── main.py                    # App entry point — CORS, lifespan, router registration
├── requirements.txt
├── .env.example
├── render.yaml                # Render.com deployment config
│
├── core/
│   ├── config.py              # All env vars via pydantic-settings
│   ├── security.py            # bcrypt, OTP generation, phone/password validation
│   └── otp_store.py           # In-memory OTP store with TTL
│
├── db/
│   ├── database.py            # asyncpg connection pool + query helpers
│   └── supabase.py            # Supabase client + file upload helper
│
├── services/
│   ├── email.py               # OTP email delivery
│   ├── falai.py               # 2D image generation with rate limiting
│   ├── meshy.py               # 3D model generation with async polling
│   └── paymongo.py            # Checkout sessions + webhook verification
│
├── routers/
│   ├── auth.py                # Login, registration, password reset, reactivation
│   ├── users.py               # User profiles + admin user management
│   ├── products.py            # Product CRUD, stock, image upload
│   ├── orders.py              # Order lifecycle, item management
│   ├── inquiries.py           # Custom quote requests + order conversion
│   ├── payments.py            # Checkout, status polling, webhook
│   ├── builder.py             # AI image/3D generation, file uploads
│   ├── reviews.py             # Reviews, ratings, admin reply, analytics
│   └── complaints.py          # Support tickets, admin management, analytics
│
└── schemas/
    ├── user.py
    ├── product.py
    ├── order.py
    ├── inquiry.py
    ├── review.py
    └── complaint.py
```

---

## Getting Started

### 1. Install dependencies

```bash
cd PrintHub_Python
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values (see [Environment Variables](#environment-variables) below).

### 3. Run the server

```bash
# Development (auto-reload)
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`  
OpenAPI schema: `http://localhost:8000/openapi.json`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in each value:

```env
# PostgreSQL — use the same Supabase credentials as the Node.js backend
DATABASE_URL=postgresql://user:pass@host:6543/db?pgbouncer=true
DIRECT_URL=postgresql://user:pass@host:5432/db

# Supabase Storage
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# PayMongo
PAYMONGO_SECRET_KEY=sk_test_xxxxx
PAYMONGO_WEBHOOK_SECRET=whsk_xxxxx
FRONTEND_URL=http://localhost:3001

# Email (optional — set both to enable OTP emails)
EMAIL_USER=your@gmail.com
EMAIL_PASS=your_app_password

# Image generation
# FAL_MOCK=true  → free Pollinations.AI (good for development)
# FAL_MOCK=false → real FAL.ai (requires FAL_KEY)
FAL_KEY=fal_xxxxx
FAL_MOCK=true

# 3D model generation
MESHY_API_KEY=your_meshy_key

# Server
PORT=8000
NODE_ENV=development
```

> **Note:** `DATABASE_URL` and `DIRECT_URL` are identical to the ones used by the Node.js backend — this service connects to the same Supabase PostgreSQL database.

---

## API Endpoints

All endpoints are prefixed with `/api`. The full list mirrors the Node.js backend exactly.

### Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/api/login` | Login with email + password |
| POST | `/api/register/send-otp` | Send registration OTP |
| POST | `/api/register/verify-otp` | Verify registration OTP |
| POST | `/api/register/complete` | Complete registration |
| POST | `/api/password/send-otp` | Send password-reset OTP |
| POST | `/api/password/verify-otp` | Verify password-reset OTP |
| POST | `/api/reset-password` | Reset password |
| POST | `/api/reactivate/verify-otp` | Reactivate archived account |

### Users
| Method | Path | Description |
|---|---|---|
| GET | `/api/user-profile/:id` | Get user profile |
| PUT | `/api/user-profile/:id` | Update user profile |
| PUT | `/api/profile/:id/password` | Change password |
| GET | `/api/admin/users` | List all users (admin) |
| POST | `/api/admin/users` | Create user (admin) |
| PUT | `/api/admin/users/:id` | Update user (admin) |
| DELETE | `/api/admin/users/:id` | Archive user (admin) |

### Products
| Method | Path | Description |
|---|---|---|
| GET | `/api/products` | List products (paginated) |
| GET | `/api/products/:id` | Get single product |
| POST | `/api/products` | Create product |
| PUT | `/api/products/:id` | Update product |
| DELETE | `/api/products/:id` | Soft-delete product |
| POST | `/api/products/:id/add-stock` | Add stock |
| POST | `/api/products/upload` | Upload product image |
| GET | `/api/admin/low-stock` | Low stock report |

### Orders
| Method | Path | Description |
|---|---|---|
| POST | `/api/orders` | Create order (deducts stock atomically) |
| GET | `/api/orders/:id` | Get order with items |
| GET | `/api/user/:id/orders` | Get user's orders |
| GET | `/api/admin/orders` | List all orders |
| PUT | `/api/orders/:id` | Update order |
| PATCH | `/api/orders/:id/deliver` | Mark as delivered |
| DELETE | `/api/orders/:id` | Soft-delete (restores stock) |
| DELETE | `/api/orders/:orderId/items/:itemId` | Remove item (restores stock) |

### Inquiries
| Method | Path | Description |
|---|---|---|
| POST | `/api/inquiries` | Submit inquiry |
| GET | `/api/inquiries` | List inquiries |
| GET | `/api/inquiries/:id` | Get inquiry |
| PUT | `/api/inquiries/:id` | Update inquiry (auto-creates order on first quote) |
| GET | `/api/user/:id/inquiries` | User's inquiries |
| PUT | `/api/inquiries/:id/convert` | Convert to order |

### Payments
| Method | Path | Description |
|---|---|---|
| POST | `/api/payments/checkout` | Create PayMongo checkout session |
| GET | `/api/payments/:orderId/status` | Get payment status |
| POST | `/api/payments/webhook` | PayMongo webhook receiver |

### AI Builder
| Method | Path | Description |
|---|---|---|
| POST | `/api/builder/upload` | Upload design file |
| POST | `/api/builder/generate-image` | Generate 2D image (FAL.ai / Pollinations) |
| POST | `/api/builder/generate` | Generate 3D model from text (Meshy) |
| POST | `/api/builder/generate-from-image` | Generate 3D model from image (Meshy) |
| POST | `/api/builder/generate-3d` | Wrap 2D texture on 3D object |
| POST | `/api/user/avatar-upload` | Upload user avatar |

### Reviews
| Method | Path | Description |
|---|---|---|
| POST | `/api/reviews` | Submit review |
| GET | `/api/products/:id/reviews` | Product reviews (names masked if anonymous) |
| GET | `/api/user/:id/reviews` | User's reviews |
| PUT | `/api/reviews/:id` | Update review |
| DELETE | `/api/reviews/:id` | Delete review |
| GET | `/api/admin/reviews` | All reviews (admin) |
| PUT | `/api/admin/reviews/:id/reply` | Admin reply |
| GET | `/api/admin/analytics/reviews` | Review analytics |

### Complaints
| Method | Path | Description |
|---|---|---|
| POST | `/api/complaints/upload-image` | Upload complaint image |
| POST | `/api/complaints` | Submit complaint |
| GET | `/api/user/:id/complaints` | User's complaints |
| GET | `/api/admin/complaints` | All complaints (admin) |
| GET | `/api/admin/complaints/:id` | Single complaint (admin) |
| PUT | `/api/admin/complaints/:id` | Update complaint (admin) |
| GET | `/api/admin/analytics/complaints` | Complaint analytics |

---

## Deployment on Render

The included `render.yaml` configures a Python web service.

1. Push this folder to a GitHub repository
2. Create a new **Web Service** on [Render](https://render.com) and connect the repo
3. Render will auto-detect `render.yaml` and configure the service
4. Add all environment variables in the Render dashboard (Settings → Environment)

The build command is `pip install -r requirements.txt` and the start command is `uvicorn main:app --host 0.0.0.0 --port $PORT`.

---

## Key Differences from Node.js Backend

| Aspect | Node.js | Python (this project) |
|---|---|---|
| Default port | 3000 | 8000 |
| ORM | Prisma | Raw asyncpg SQL |
| Async model | Event loop (native) | asyncio |
| Auto-docs | None | `/docs` (Swagger UI) |
| Column name | camelCase via Prisma | snake_case (raw DB) |

> **Same database** — both backends connect to the same PostgreSQL instance. You can run them in parallel without any data migration.

---

## Frontend Changes Required

The frontend at `PrintHub_FrontEnd` currently points to the Node.js backend. To switch to this Python backend, you only need to update the API base URL. Here is exactly what to change:

### 1. `.env.development` — for local development

**File:** `PrintHub_FrontEnd/.env.development`

```diff
- REACT_APP_API_URL=https://printhub-backend-jdv8.onrender.com
+ REACT_APP_API_URL=http://localhost:8000
```

> Use `http://localhost:8000` when running the Python server locally.  
> Use `http://10.0.2.2:8000` if testing on an Android emulator.

### 2. `.env` — for production

**File:** `PrintHub_FrontEnd/.env`

Once you deploy this Python backend to Render (or any host), update the production URL:

```diff
- REACT_APP_API_URL=https://printhub-backend-jdv8.onrender.com
+ REACT_APP_API_URL=https://YOUR-NEW-PYTHON-API-URL.onrender.com
```

Replace `YOUR-NEW-PYTHON-API-URL` with the actual URL Render assigns to this service.

### 3. No other frontend changes needed

The Python backend is a **drop-in replacement**:
- All endpoint paths are identical (`/api/login`, `/api/products`, etc.)
- All request/response JSON shapes are identical
- The frontend's `src/config/api.js` already reads `REACT_APP_API_URL` from the environment, so changing those two `.env` files is the only step required

### Quick checklist

- [ ] Update `PrintHub_FrontEnd/.env.development` → `http://localhost:8000`
- [ ] Start the Python server: `uvicorn main:app --reload --port 8000`
- [ ] Start the frontend: `npm start` inside `PrintHub_FrontEnd`
- [ ] Verify login works at `http://localhost:3001`
- [ ] When deploying: update `PrintHub_FrontEnd/.env` with the new Render URL

---

## Notes

- **OTP emails** are disabled by default. Set `EMAIL_USER` and `EMAIL_PASS` to enable them. OTPs are printed to the server console when SMTP is disabled — useful for testing.
- **AI image generation** defaults to free Pollinations.AI (`FAL_MOCK=true`). Set `FAL_MOCK=false` and provide `FAL_KEY` for production FAL.ai.
- **In-memory OTP store** is fine for a single-process deployment. For multi-instance setups, replace `core/otp_store.py` with a Redis-backed implementation.
- **Interactive API docs** are available at `/docs` — useful for testing all endpoints without a client.
