# AlakhService

A simple Node.js REST API service.

## Getting Started

### Install dependencies

```bash
npm install
```

### Run the service

```bash
npm start
```

The service will start on port `3000` by default. Set the `PORT` environment variable to use a different port.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/items` | List all items |
| GET | `/api/items/:id` | Get item by ID |
| POST | `/api/items` | Create a new item |
| PUT | `/api/items/:id` | Update an item |
| DELETE | `/api/items/:id` | Delete an item |

## Testing

```bash
npm test
```