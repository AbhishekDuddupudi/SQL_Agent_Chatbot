"""
Stub SQL Agent - Intent Router for generating SQL queries
This is a simple rule-based router that will be replaced with LLM-based routing later.
"""
from typing import Dict, Any, Optional, List
import re


def route_intent(message: str) -> Dict[str, Any]:
    """
    Route user intent to appropriate SQL query or follow-up questions.
    
    Args:
        message: The user's natural language question
        
    Returns:
        Dict containing either:
        - {"sql": <query>, "assumptions": [...]} for recognized intents
        - {"sql": None, "follow_up_questions": [...]} for unclear intents
    """
    message_lower = message.lower().strip()
    
    # Intent: Top products by revenue
    if _matches_intent(message_lower, ["top product", "best product", "top selling"]) and \
       _matches_intent(message_lower, ["revenue", "sales", "selling"]):
        return {
            "sql": """
SELECT 
    p.name as product_name,
    SUM(s.revenue) as total_revenue,
    SUM(s.quantity) as total_quantity
FROM sales s
JOIN product p ON s.product_id = p.id
GROUP BY p.id, p.name
ORDER BY total_revenue DESC
LIMIT 10
            """.strip(),
            "assumptions": [
                "Showing top 10 products by total revenue",
                "Revenue includes all territories and time periods",
                "Sorted by highest revenue first"
            ],
            "follow_up_questions": []
        }
    
    # Intent: Revenue by territory
    if _matches_intent(message_lower, ["revenue", "sales"]) and \
       _matches_intent(message_lower, ["territory", "region", "area"]):
        return {
            "sql": """
SELECT 
    t.name as territory_name,
    t.region,
    SUM(s.revenue) as total_revenue,
    COUNT(s.id) as transaction_count
FROM sales s
JOIN territory t ON s.territory_id = t.id
GROUP BY t.id, t.name, t.region
ORDER BY total_revenue DESC
            """.strip(),
            "assumptions": [
                "Aggregating revenue across all products",
                "Including all time periods in the data",
                "Grouped by territory with region information"
            ],
            "follow_up_questions": []
        }
    
    # Intent: Show recent sales
    if _matches_intent(message_lower, ["show sales", "list sales", "recent sales", "all sales", "sales data"]):
        return {
            "sql": """
SELECT 
    s.id,
    p.name as product_name,
    t.name as territory_name,
    h.first_name || ' ' || h.last_name as hcp_name,
    s.quantity,
    s.revenue,
    s.sale_date
FROM sales s
JOIN product p ON s.product_id = p.id
JOIN territory t ON s.territory_id = t.id
JOIN hcp h ON s.hcp_id = h.id
ORDER BY s.sale_date DESC
LIMIT 50
            """.strip(),
            "assumptions": [
                "Showing most recent 50 sales transactions",
                "Including product, territory, and HCP details",
                "Sorted by date with newest first"
            ],
            "follow_up_questions": []
        }
    
    # Intent: Products list
    if _matches_intent(message_lower, ["list product", "all product", "show product", "what product"]):
        return {
            "sql": """
SELECT 
    id,
    name,
    category,
    unit_price
FROM product
ORDER BY name
            """.strip(),
            "assumptions": [
                "Listing all available products",
                "Sorted alphabetically by name"
            ],
            "follow_up_questions": []
        }
    
    # Intent: HCP/Doctor information
    if _matches_intent(message_lower, ["hcp", "doctor", "healthcare", "physician"]):
        return {
            "sql": """
SELECT 
    h.id,
    h.first_name || ' ' || h.last_name as name,
    h.specialty,
    t.name as territory,
    h.email
FROM hcp h
JOIN territory t ON h.territory_id = t.id
ORDER BY h.last_name, h.first_name
            """.strip(),
            "assumptions": [
                "Listing all healthcare professionals",
                "Including their specialty and territory",
                "Sorted by name"
            ],
            "follow_up_questions": []
        }
    
    # Intent: Territory list
    if _matches_intent(message_lower, ["list territor", "all territor", "show territor", "what territor"]):
        return {
            "sql": """
SELECT 
    id,
    name,
    region,
    country
FROM territory
ORDER BY region, name
            """.strip(),
            "assumptions": [
                "Listing all territories",
                "Sorted by region and name"
            ],
            "follow_up_questions": []
        }
    
    # Unknown intent - return follow-up questions
    return {
        "sql": None,
        "assumptions": [],
        "follow_up_questions": [
            "What are the top products by revenue?",
            "Show me revenue breakdown by territory",
            "Can you list recent sales transactions?"
        ]
    }


def _matches_intent(text: str, keywords: List[str]) -> bool:
    """Check if any of the keywords appear in the text."""
    return any(kw in text for kw in keywords)
