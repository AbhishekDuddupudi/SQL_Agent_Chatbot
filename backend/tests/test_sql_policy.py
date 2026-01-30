"""
Tests for SQL policy guardrails.
"""
import pytest

from app.guardrails.sql_policy import validate_sql, SQLPolicyError


class TestSQLPolicy:
    """Tests for SQL policy validation."""
    
    def test_adds_default_limit(self):
        """Query without LIMIT should get default added."""
        sql = "SELECT name FROM product"
        result = validate_sql(sql)
        assert "LIMIT" in result.upper()
    
    def test_caps_high_limit(self):
        """LIMIT higher than max should be capped."""
        sql = "SELECT name FROM product LIMIT 1000"
        result = validate_sql(sql)
        assert "LIMIT 200" in result
    
    def test_keeps_reasonable_limit(self):
        """LIMIT under max should be kept."""
        sql = "SELECT name FROM product LIMIT 50"
        result = validate_sql(sql)
        assert "LIMIT 50" in result
    
    def test_rejects_insert(self):
        """INSERT should be rejected."""
        sql = "INSERT INTO product (name) VALUES ('test')"
        with pytest.raises(SQLPolicyError):
            validate_sql(sql)
    
    def test_rejects_update(self):
        """UPDATE should be rejected."""
        sql = "UPDATE product SET name = 'test'"
        with pytest.raises(SQLPolicyError):
            validate_sql(sql)
    
    def test_rejects_delete(self):
        """DELETE should be rejected."""
        sql = "DELETE FROM product WHERE id = 1"
        with pytest.raises(SQLPolicyError):
            validate_sql(sql)
    
    def test_rejects_drop(self):
        """DROP should be rejected."""
        sql = "DROP TABLE product"
        with pytest.raises(SQLPolicyError):
            validate_sql(sql)
    
    def test_rejects_multiple_statements(self):
        """Multiple statements should be rejected."""
        sql = "SELECT 1; SELECT 2"
        with pytest.raises(SQLPolicyError):
            validate_sql(sql)
    
    def test_strips_trailing_semicolon(self):
        """Trailing semicolon should be handled."""
        sql = "SELECT name FROM product;"
        result = validate_sql(sql)
        assert not result.rstrip().endswith(';')
    
    def test_rejects_negative_limit(self):
        """Negative LIMIT should be rejected."""
        sql = "SELECT name FROM product LIMIT -1"
        with pytest.raises(SQLPolicyError):
            validate_sql(sql)
    
    def test_valid_join_query(self):
        """Valid JOIN query should pass."""
        sql = """
        SELECT p.name, SUM(s.revenue)
        FROM product p
        JOIN sales s ON p.id = s.product_id
        GROUP BY p.id, p.name
        ORDER BY SUM(s.revenue) DESC
        """
        result = validate_sql(sql)
        assert "SELECT" in result.upper()
        assert "JOIN" in result.upper()
