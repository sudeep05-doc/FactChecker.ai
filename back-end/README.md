# VerifyAI backend

The VerifyAI backend is an Express and MongoDB API for accounts, authentication,
verification history, reports, feedback, notifications, news, and admin
analytics. It uses Mongoose for persistence, bcryptjs for password hashing, and
JWTs for authenticated requests.

## Requirements

- Node.js 18 LTS or newer (Node.js 20 LTS recommended)
- npm
- A MongoDB Atlas cluster or local MongoDB server

## Install and run

```bash
cd back-end
npm install
copy .env.example .env
# Edit .env and add MONGO_URI and JWT_SECRET
npm run dev
```

For production, run `npm start`. The default API URL is
`http://localhost:5000` and the health check is
`GET http://localhost:5000/api/health`.

## Configure MongoDB Atlas

1. Create a cluster at MongoDB Atlas.
2. In **Database Access**, create a database user with a password.
3. In **Network Access**, add the IP addresses allowed to connect (use your
   current IP for development).
4. Choose **Connect > Drivers** and copy the connection string.
5. Put it in `back-end/.env`, using the `verifyai` database, for example:

```env
MONGO_URI=mongodb+srv://USERNAME@CLUSTER.mongodb.net/verifyai
```

The application explicitly selects `verifyai`, so a connection string without a
database path also works. Never put a real password or Atlas URI in this README,
`.env.example`, or GitHub.

Generate a secure JWT secret with a password manager or Node.js:

```bash
node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"
```

Add its output to `JWT_SECRET` in `.env`. Set `CLIENT_URL` to the React app's
origin. Multiple origins may be comma-separated.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `MONGO_URI` | Yes | MongoDB Atlas or local connection string |
| `JWT_SECRET` | Yes | Secret used to sign access tokens |
| `PORT` | No | API port; defaults to `5000` |
| `CLIENT_URL` | Yes | Allowed frontend origin(s) |
| `EXTERNAL_API_KEY`, `AI_API_KEY`, `NEWS_API_KEY`, `STORAGE_API_KEY` | No | Reserved, disabled future integrations |

## API routes

| Prefix | Purpose |
| --- | --- |
| `/api/health` | API and database connection status |
| `/api/auth` | Register, login, current user, logout |
| `/api/users` | Authenticated profile retrieval and update |
| `/api/verification` | Run, list, retrieve, and delete verification history |
| `/api/news` | Public news retrieval; admin-only creation |
| `/api/reports` | Authenticated report submission and retrieval |
| `/api/feedback` | Feedback submission and authenticated retrieval |
| `/api/notifications` | User notifications and read state |
| `/api/admin` | Admin users, data lists, dashboard, and analytics |

## MongoDB collections

Mongoose creates these collections when records are saved: `users`,
`verifications`, `reports`, `feedback`, `notifications`, and `news`. References
use ObjectIds: verification, report, feedback, notification, and news records
can link to a user; reports and feedback can link to a verification.

## Troubleshooting

- **"MongoDB connection failed"**: confirm `MONGO_URI`, the Atlas database user,
  its password, and Network Access rules.
- **"JWT_SECRET is not set"**: add a non-empty random value to `.env`.
- **CORS request blocked**: make `CLIENT_URL` exactly match the React origin,
  including protocol and port, then restart the API.
- **Port already in use**: change `PORT` or stop the process using that port.

## Security

`.env`, `node_modules/`, uploads, and logs are ignored by Git. Do not commit
credentials, JWT secrets, access tokens, or API keys. Passwords are hashed with
bcryptjs and are never returned by the API. The first registered account becomes
an admin in the existing application; create it deliberately and protect its
credentials.
