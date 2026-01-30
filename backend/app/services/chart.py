"""
Vega-Lite chart specification generator.
"""
from typing import List, Dict, Any, Optional


def generate_chart_spec(
    columns: List[str],
    rows: List[Dict[str, Any]],
    sql: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Vega-Lite specification based on query results.
    
    Args:
        columns: Column names from the result
        rows: Result data as list of dicts
        sql: The SQL query (for context)
        
    Returns:
        Vega-Lite specification dict, or empty dict if no chart is appropriate
    """
    if not rows or not columns:
        return {}
    
    # Limit data for visualization
    display_data = rows[:50]
    
    # Identify column types
    numeric_cols = []
    categorical_cols = []
    date_cols = []
    
    first_row = rows[0]
    for col in columns:
        val = first_row.get(col)
        if val is None:
            # Check other rows for non-null values
            for row in rows[:10]:
                if row.get(col) is not None:
                    val = row.get(col)
                    break
        
        if val is None:
            categorical_cols.append(col)
        elif isinstance(val, (int, float)):
            numeric_cols.append(col)
        elif _is_date_like(col, val):
            date_cols.append(col)
        else:
            categorical_cols.append(col)
    
    # Decide chart type based on data shape
    chart_spec = _select_chart_type(
        display_data, columns, numeric_cols, categorical_cols, date_cols, sql
    )
    
    return chart_spec


def _is_date_like(col_name: str, value: Any) -> bool:
    """Check if a column appears to be date-like."""
    col_lower = col_name.lower()
    date_keywords = ['date', 'time', 'created', 'updated', 'timestamp', 'month', 'year']
    
    if any(kw in col_lower for kw in date_keywords):
        return True
    
    if isinstance(value, str):
        # Simple date pattern check
        if len(value) >= 8 and ('-' in value or '/' in value):
            return True
    
    return False


def _select_chart_type(
    data: List[Dict[str, Any]],
    columns: List[str],
    numeric_cols: List[str],
    categorical_cols: List[str],
    date_cols: List[str],
    sql: Optional[str]
) -> Dict[str, Any]:
    """Select and build appropriate chart type."""
    
    # Skip charts for very small or very large datasets
    if len(data) < 2 or len(data) > 100:
        if len(data) > 100:
            data = data[:50]
        elif len(data) < 2:
            return {}
    
    # Time series: date column + numeric column
    if date_cols and numeric_cols:
        return _build_line_chart(data, date_cols[0], numeric_cols[0])
    
    # Bar chart: categorical + numeric
    if categorical_cols and numeric_cols:
        # Prefer revenue/sales/count columns
        y_col = _pick_best_numeric(numeric_cols)
        x_col = _pick_best_categorical(categorical_cols)
        return _build_bar_chart(data, x_col, y_col)
    
    # Just numeric columns: simple bar chart with index
    if numeric_cols and len(data) <= 20:
        # Use first column as label if it's text-like
        if columns and columns[0] in categorical_cols:
            return _build_bar_chart(data, columns[0], numeric_cols[0])
    
    return {}


def _pick_best_numeric(cols: List[str]) -> str:
    """Pick the most relevant numeric column for visualization."""
    priority_keywords = ['revenue', 'total', 'sum', 'count', 'sales', 'amount', 'quantity']
    
    for keyword in priority_keywords:
        for col in cols:
            if keyword in col.lower():
                return col
    
    return cols[0]


def _pick_best_categorical(cols: List[str]) -> str:
    """Pick the most relevant categorical column for visualization."""
    priority_keywords = ['name', 'product', 'territory', 'category', 'region', 'label']
    
    for keyword in priority_keywords:
        for col in cols:
            if keyword in col.lower():
                return col
    
    # Avoid id columns
    non_id_cols = [c for c in cols if 'id' not in c.lower()]
    return non_id_cols[0] if non_id_cols else cols[0]


def _build_bar_chart(
    data: List[Dict[str, Any]],
    x_field: str,
    y_field: str
) -> Dict[str, Any]:
    """Build a bar chart specification."""
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Query Results",
        "data": {"values": _sanitize_data(data)},
        "mark": "bar",
        "encoding": {
            "x": {
                "field": x_field,
                "type": "nominal",
                "sort": "-y",
                "axis": {"labelAngle": -45}
            },
            "y": {
                "field": y_field,
                "type": "quantitative"
            },
            "tooltip": [
                {"field": x_field, "type": "nominal"},
                {"field": y_field, "type": "quantitative", "format": ",.2f"}
            ]
        },
        "width": "container",
        "height": 300
    }


def _build_line_chart(
    data: List[Dict[str, Any]],
    x_field: str,
    y_field: str
) -> Dict[str, Any]:
    """Build a line chart specification."""
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Query Results Over Time",
        "data": {"values": _sanitize_data(data)},
        "mark": {"type": "line", "point": True},
        "encoding": {
            "x": {
                "field": x_field,
                "type": "temporal",
                "axis": {"labelAngle": -45}
            },
            "y": {
                "field": y_field,
                "type": "quantitative"
            },
            "tooltip": [
                {"field": x_field, "type": "temporal"},
                {"field": y_field, "type": "quantitative", "format": ",.2f"}
            ]
        },
        "width": "container",
        "height": 300
    }


def _sanitize_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sanitize data for JSON serialization."""
    sanitized = []
    for row in data:
        clean_row = {}
        for k, v in row.items():
            # Convert Decimal to float, dates to strings
            if hasattr(v, '__float__'):
                clean_row[k] = float(v)
            elif hasattr(v, 'isoformat'):
                clean_row[k] = v.isoformat()
            else:
                clean_row[k] = v
        sanitized.append(clean_row)
    return sanitized
