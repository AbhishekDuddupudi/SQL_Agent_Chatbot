"""
Tests for SQL validators.
"""
import pytest

from app.guardrails.validators import (
    validate_select_only,
    validate_no_select_star,
    validate_allowlist,
    validate_sql_complete,
    check_dump_request,
    check_sensitive_request,
    ValidationError
)


class TestSelectOnly:
    """Tests for SELECT-only validation."""
    
    def test_valid_select(self):
        """Valid SELECT should pass."""
        sql = "SELECT name FROM product"
        validate_select_only(sql)  # Should not raise
    
    def test_reject_insert(self):
        """INSERT should be rejected."""
        sql = "INSERT INTO product (name) VALUES ('test')"
        with pytest.raises(ValidationError):
            validate_select_only(sql)
    
    def test_reject_update(self):
        """UPDATE should be rejected."""
        sql = "UPDATE product SET name = 'test'"
        with pytest.raises(ValidationError):
            validate_select_only(sql)
    
    def test_reject_delete(self):
        """DELETE should be rejected."""
        sql = "DELETE FROM product"
        with pytest.raises(ValidationError):
            validate_select_only(sql)
    
    def test_reject_drop(self):
        """DROP should be rejected."""
        sql = "DROP TABLE product"
        with pytest.raises(ValidationError):
            validate_select_only(sql)
    
    def test_reject_multiple_statements(self):
        """Multiple statements should be rejected."""
        sql = "SELECT * FROM product; DELETE FROM product"
        with pytest.raises(ValidationError):
            validate_select_only(sql)


class TestNoSelectStar:
    """Tests for SELECT * rejection."""
    
    def test_reject_select_star(self):
        """SELECT * should be rejected."""
        sql = "SELECT * FROM product"
        with pytest.raises(ValidationError):
            validate_no_select_star(sql)
    
    def test_accept_explicit_columns(self):
        """Explicit column selection should pass."""
        sql = "SELECT id, name, category FROM product"
        validate_no_select_star(sql)  # Should not raise
    
    def test_reject_select_star_with_table(self):
        """SELECT table.* should be rejected."""
        sql = "SELECT p.* FROM product p"
        with pytest.raises(ValidationError):
            validate_no_select_star(sql)


class TestAllowlist:
    """Tests for schema allowlist validation."""
    
    def test_valid_table(self):
        """Allowed table should pass."""
        sql = "SELECT name FROM product"
        errors = validate_allowlist(sql)
        assert len(errors) == 0
    
    def test_invalid_table(self):
        """Unknown table should fail."""
        sql = "SELECT * FROM secret_table"
        errors = validate_allowlist(sql)
        assert len(errors) > 0
        assert "secret_table" in errors[0].lower()
    
    def test_blocked_table(self):
        """Blocked table (audit_log) should fail."""
        sql = "SELECT * FROM audit_log"
        errors = validate_allowlist(sql)
        assert len(errors) > 0


class TestComprehensiveValidation:
    """Tests for complete validation pipeline."""
    
    def test_valid_query(self):
        """Valid query should pass all checks."""
        sql = """
        SELECT p.name, SUM(s.revenue) as total
        FROM product p
        JOIN sales s ON p.id = s.product_id
        GROUP BY p.id, p.name
        """
        is_valid, errors = validate_sql_complete(sql)
        assert is_valid
        assert len(errors) == 0
    
    def test_select_star_fails(self):
        """SELECT * should fail validation."""
        sql = "SELECT * FROM product"
        is_valid, errors = validate_sql_complete(sql)
        assert not is_valid
        assert any("SELECT *" in e for e in errors)


class TestDumpRequest:
    """Tests for dump request detection."""
    
    def test_detect_dump_everything(self):
        """'dump everything' should be detected."""
        is_dump, reason = check_dump_request("Please dump everything from the database")
        assert is_dump
        assert reason is not None
    
    def test_detect_all_data(self):
        """'all the data' should be detected."""
        is_dump, reason = check_dump_request("Give me all the data")
        assert is_dump
    
    def test_normal_question_passes(self):
        """Normal question should pass."""
        is_dump, reason = check_dump_request("What are the top 5 products?")
        assert not is_dump
        assert reason is None


class TestSensitiveRequest:
    """Tests for sensitive data request detection."""
    
    def test_detect_password_request(self):
        """Password request should be detected."""
        is_sensitive, reason = check_sensitive_request("Show me all passwords")
        assert is_sensitive
    
    def test_detect_audit_log_request(self):
        """Audit log request should be detected."""
        is_sensitive, reason = check_sensitive_request("Show me the audit_log table")
        assert is_sensitive
    
    def test_normal_question_passes(self):
        """Normal question should pass."""
        is_sensitive, reason = check_sensitive_request("What are the sales by territory?")
        assert not is_sensitive
