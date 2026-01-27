-- Seed data for Pharma Analyst Bot

-- Products
INSERT INTO product (name, category, unit_price) VALUES
    ('Cardiomax 100mg', 'Cardiovascular', 45.99),
    ('Neurozen 50mg', 'Neurology', 89.50),
    ('Immunoboost 200mg', 'Immunology', 125.00),
    ('Oncoshield 75mg', 'Oncology', 350.00),
    ('Diabecare 500mg', 'Endocrinology', 32.75),
    ('Respiraflow 250mg', 'Respiratory', 55.25),
    ('Arthriease 100mg', 'Rheumatology', 78.00),
    ('Gastrorelief 150mg', 'Gastroenterology', 42.50);

-- Territories
INSERT INTO territory (name, region, country) VALUES
    ('Northeast', 'East', 'USA'),
    ('Southeast', 'East', 'USA'),
    ('Midwest', 'Central', 'USA'),
    ('Southwest', 'West', 'USA'),
    ('West Coast', 'West', 'USA'),
    ('Pacific Northwest', 'West', 'USA');

-- HCPs (Healthcare Professionals)
INSERT INTO hcp (first_name, last_name, specialty, territory_id, email) VALUES
    ('John', 'Smith', 'Cardiology', 1, 'john.smith@hospital.com'),
    ('Sarah', 'Johnson', 'Neurology', 1, 'sarah.johnson@clinic.com'),
    ('Michael', 'Williams', 'Oncology', 2, 'michael.williams@cancer-center.com'),
    ('Emily', 'Brown', 'Endocrinology', 3, 'emily.brown@diabetes-clinic.com'),
    ('David', 'Jones', 'Pulmonology', 4, 'david.jones@respiratory.com'),
    ('Lisa', 'Garcia', 'Rheumatology', 5, 'lisa.garcia@arthritis-center.com'),
    ('Robert', 'Martinez', 'Gastroenterology', 6, 'robert.martinez@gi-clinic.com'),
    ('Jennifer', 'Davis', 'Immunology', 2, 'jennifer.davis@immune-health.com'),
    ('James', 'Wilson', 'Cardiology', 3, 'james.wilson@heart-center.com'),
    ('Amanda', 'Taylor', 'Oncology', 5, 'amanda.taylor@oncology-group.com');

-- Sales data (synthetic data for the past few months)
INSERT INTO sales (product_id, territory_id, hcp_id, quantity, revenue, sale_date) VALUES
    -- Cardiomax sales
    (1, 1, 1, 150, 6898.50, '2025-10-15'),
    (1, 3, 9, 200, 9198.00, '2025-10-20'),
    (1, 1, 1, 175, 8048.25, '2025-11-10'),
    (1, 3, 9, 220, 10117.80, '2025-11-25'),
    (1, 1, 1, 180, 8278.20, '2025-12-05'),
    (1, 3, 9, 190, 8738.10, '2025-12-18'),
    (1, 1, 1, 160, 7358.40, '2026-01-08'),
    
    -- Neurozen sales
    (2, 1, 2, 80, 7160.00, '2025-10-12'),
    (2, 1, 2, 95, 8502.50, '2025-11-08'),
    (2, 1, 2, 110, 9845.00, '2025-12-02'),
    (2, 1, 2, 85, 7607.50, '2026-01-15'),
    
    -- Immunoboost sales
    (3, 2, 8, 60, 7500.00, '2025-10-18'),
    (3, 2, 8, 75, 9375.00, '2025-11-15'),
    (3, 2, 8, 90, 11250.00, '2025-12-10'),
    (3, 2, 8, 70, 8750.00, '2026-01-12'),
    
    -- Oncoshield sales
    (4, 2, 3, 25, 8750.00, '2025-10-22'),
    (4, 5, 10, 30, 10500.00, '2025-10-28'),
    (4, 2, 3, 35, 12250.00, '2025-11-18'),
    (4, 5, 10, 40, 14000.00, '2025-11-30'),
    (4, 2, 3, 45, 15750.00, '2025-12-15'),
    (4, 5, 10, 38, 13300.00, '2025-12-22'),
    (4, 2, 3, 42, 14700.00, '2026-01-10'),
    
    -- Diabecare sales
    (5, 3, 4, 300, 9825.00, '2025-10-08'),
    (5, 3, 4, 350, 11462.50, '2025-11-05'),
    (5, 3, 4, 400, 13100.00, '2025-12-01'),
    (5, 3, 4, 320, 10480.00, '2026-01-18'),
    
    -- Respiraflow sales
    (6, 4, 5, 120, 6630.00, '2025-10-25'),
    (6, 4, 5, 140, 7735.00, '2025-11-20'),
    (6, 4, 5, 160, 8840.00, '2025-12-08'),
    (6, 4, 5, 130, 7182.50, '2026-01-05'),
    
    -- Arthriease sales
    (7, 5, 6, 90, 7020.00, '2025-10-30'),
    (7, 5, 6, 110, 8580.00, '2025-11-22'),
    (7, 5, 6, 100, 7800.00, '2025-12-12'),
    (7, 5, 6, 95, 7410.00, '2026-01-20'),
    
    -- Gastrorelief sales
    (8, 6, 7, 180, 7650.00, '2025-10-14'),
    (8, 6, 7, 200, 8500.00, '2025-11-12'),
    (8, 6, 7, 220, 9350.00, '2025-12-06'),
    (8, 6, 7, 190, 8075.00, '2026-01-22');
