-- Authentication tables for user login system

-- Users table (stores registered users)
CREATE TABLE IF NOT EXISTS app_user (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sessions table (server-side session storage)
CREATE TABLE IF NOT EXISTS user_session (
    id VARCHAR(64) PRIMARY KEY,  -- session token (UUID)
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Index for session lookup and cleanup
CREATE INDEX IF NOT EXISTS idx_session_user ON user_session(user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires ON user_session(expires_at);

-- Seed demo user
-- Password: "demo123" hashed with bcrypt
INSERT INTO app_user (email, password_hash, display_name) VALUES
    ('demo@example.com', '$2b$12$ma.hkyQbZ3QsN/zei5H1Z.VbC2ki/FtXflSizcorf7Y.ac90KEWcW', 'Demo User')
ON CONFLICT (email) DO NOTHING;
