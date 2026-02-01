# SQL Agent Chatbot - Pharma Analytics POC

A LangGraph-based Text-to-SQL agent for pharmaceutical analytics, built with FastAPI, PostgreSQL, and React.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![React](https://img.shields.io/badge/React-18+-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.0.26+-purple)

## ✨ Features

- **Natural Language to SQL**: Ask questions in plain English and get SQL queries automatically generated
- **LangGraph Workflow**: Multi-step agent with preprocessing, validation, retry logic, and summarization
- **Guardrails & Safety**: 
  - SELECT-only queries (no DDL/DML)
  - No SELECT * allowed
  - Schema allowlist enforcement
  - Dangerous pattern detection
  - Sensitive data protection
- **Vega-Lite Charts**: Automatic visualization of query results (bar, line, pie charts)
- **Collapsible Chart Display**: Charts shown on-demand with smooth scrolling
- **Audit Logging**: Every request is logged for compliance and debugging
- **LLM-Based Summarization**: Business-friendly answers powered by OpenAI GPT-4

## 🏗️ Architecture

### LangGraph Workflow

The agent uses a sophisticated 9-node LangGraph workflow with multiple decision points and retry logic:

![Workflow Diagram](workflow_diagram.png)

### Workflow Components

| Node | Description |
|------|-------------|
| **Preprocess** | Normalizes user question (whitespace, punctuation) |
| **Scope & Policy** | Checks for sensitive/disallowed requests and ambiguity |
| **Clarify** | Generates clarifying questions for ambiguous input |
| **Schema Ground** | Maps question to relevant database tables/columns |
| **Generate SQL** | Uses OpenAI LLM to generate PostgreSQL query |
| **Validate SQL** | Enforces SELECT-only, no SELECT *, schema allowlist |
| **Fix & Retry** | Attempts to fix invalid SQL (max 3 retries) |
| **Execute** | Runs validated SQL against PostgreSQL database |
| **Finalize** | Generates LLM summary, Vega-Lite chart, follow-up questions |

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  React Frontend │────▶│  FastAPI Backend│────▶│   PostgreSQL    │
│  (Vite + TS)    │     │  (LangGraph)    │     │   Database      │
│                 │◀────│                 │◀────│                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   OpenAI API    │
                        │    (GPT-4)      │
                        └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API Key ([Get one here](https://platform.openai.com/api-keys))

### Setup Instructions

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
   ```env
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

## 🧪 Testing

Run backend tests:
```bash
cd backend
pytest tests/ -v
```

## 🔧 Development

### Regenerate Workflow Diagram

To regenerate the workflow diagram PNG:

```bash
# Activate virtual environment
source .venv/bin/activate

# Generate the diagram
python backend/generate_workflow_graph.py
```

This will create `workflow_diagram.png` in the project root.

**Requirements for PNG generation:**
- macOS: `brew install graphviz`
- Ubuntu: `sudo apt-get install graphviz`
- Python: `pip install pygraphviz`

### Running Locally (Without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Database:**
```bash
# Use Docker for PostgreSQL
docker compose up db
```

## 🐛 Troubleshooting

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

### Charts not displaying
- Click "📈 Show Chart" button to display the chart
- Check browser console (F12) for JavaScript errors
- Verify the backend response includes `chart.vega_lite_spec`

## 📄 License

MIT
