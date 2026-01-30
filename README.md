# SQL Agent Chatbot - Pharma Analytics POC

A LangGraph-based Text-to-SQL agent for pharmaceutical analytics, built with FastAPI, PostgreSQL, and React.

## Features

- **Natural Language to SQL**: Ask questions in plain English and get SQL queries automatically generated
- **LangGraph Workflow**: Multi-step agent with preprocessing, validation, retry logic, and summarization
- **Guardrails & Safety**: 
  - SELECT-only queries (no DDL/DML)
  - No SELECT * allowed
  - Schema allowlist enforcement
  - Dangerous pattern detection
  - Sensitive data protection
- **Vega-Lite Charts**: Automatic visualization of query results
- **Audit Logging**: Every request is logged for compliance and debugging
- **LLM-Based Summarization**: Business-friendly answers powered by OpenAI

## Architecture

```
User Question
    │
    ▼
┌─────────────────────┐
│ Preprocess & Normalize │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Scope & Policy Check │──▶ Refuse (if disallowed)
└─────────────────────┘
    │ ambiguous?
    ▼
┌─────────────────────┐
│ Clarifying Questions │──▶ END (sql=null, follow_ups filled)
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Schema Grounding     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Generate SQL (LLM)   │◀──┐
└─────────────────────┘    │
    │                      │
    ▼                      │
┌─────────────────────┐    │
│ Validate SQL         │    │
└─────────────────────┘    │
    │ error?               │
    ▼                      │
┌─────────────────────┐    │
│ Fix & Retry (max 3)  │───┘
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Execute Query        │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Finalize Response    │
│ (LLM Summary + Chart)│
└─────────────────────┘
    │
    ▼
   END
```

## Prerequisites

- Docker and Docker Compose
- OpenAI API Key (required for LLM-based SQL generation and summarization)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd SQL_Agent_Chatbot
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

3. **Start the application**
   ```bash
   docker compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | **Yes** | - |
| `POSTGRES_USER` | Database username | Yes | `pharma_user` |
| `POSTGRES_PASSWORD` | Database password | Yes | `pharma_secret_123` |
| `POSTGRES_DB` | Database name | Yes | `pharma_db` |
| `DATABASE_URL` | Full database connection string | Yes | See `.env.example` |

## Example Questions

Try these questions to test the system:

1. **Top Products**: "What are the top 5 products by revenue?"
2. **Territory Analysis**: "Show me revenue by territory"
3. **Sales Data**: "List recent sales transactions"
4. **HCP Information**: "Show me all healthcare professionals and their specialties"
5. **Product List**: "What products are available?"
6. **Time-based**: "What were the sales in December 2025?"

## API Endpoints

### GET /api/health
Returns health status of the API.

**Response:**
```json
{
  "status": "ok"
}
```

### POST /api/chat
Process a natural language question and return SQL results.

**Request:**
```json
{
  "session_id": "optional-uuid",
  "message": "What are the top products by revenue?"
}
```

**Response:**
```json
{
  "answer": "The top product by revenue is Oncoshield 75mg with $89,250.00...",
  "sql": "SELECT p.name AS product_name, SUM(s.revenue) AS total_revenue...",
  "assumptions": ["Results sorted by highest revenue first"],
  "chart": {
    "vega_lite_spec": { ... }
  },
  "follow_up_questions": ["How does this compare by territory?"],
  "metadata": {
    "row_count": 8,
    "runtime_ms": 1234
  }
}
```

## Database Schema

The system includes a pharmaceutical sales database with:

- **product**: Drug products (id, name, category, unit_price)
- **territory**: Sales territories (id, name, region, country)
- **hcp**: Healthcare professionals (id, first_name, last_name, specialty, territory_id)
- **sales**: Sales transactions (id, product_id, territory_id, hcp_id, quantity, revenue, sale_date)

## Governance Rules

The system enforces strict governance:

1. **SELECT Only**: No INSERT, UPDATE, DELETE, DROP, or any DDL/DML
2. **No SELECT ***: Explicit column selection required
3. **Schema Allowlist**: Only approved tables/columns can be queried
4. **Case-Insensitive Filtering**: Text filters use LOWER() for matching
5. **Data Dump Protection**: Requests to "dump everything" are refused
6. **Sensitive Data Protection**: Audit logs and system tables are blocked

## Development

### Local Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://pharma_user:pharma_secret_123@localhost:5432/pharma_db"
export OPENAI_API_KEY="your-key"
uvicorn app.main:app --reload
```

### Local Frontend Development
```bash
cd frontend
npm install
npm run dev
```

## Troubleshooting

### "LLM summarization is required but not available"
- Ensure `OPENAI_API_KEY` is set in your `.env` file
- Verify the API key is valid at https://platform.openai.com

### Database connection errors
- Ensure the database container is running: `docker compose ps`
- Check database logs: `docker compose logs db`

### Frontend not connecting to backend
- Verify backend is running: `curl http://localhost:8000/api/health`
- Check the Vite proxy configuration in `frontend/vite.config.ts`

### Query validation errors
- The system only allows SELECT queries
- Avoid SELECT * - specify columns explicitly
- Check that table/column names match the schema

## Testing

Run backend tests:
```bash
cd backend
pytest tests/ -v
```

## License

MIT
