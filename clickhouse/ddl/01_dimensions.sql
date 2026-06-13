-- ============================================================
-- 01: Dimension tables (conformed dimensions of the star schema)
--
-- SCD-1 dims (merchants/devices/customers) use ReplacingMergeTree(updated_at)
-- so the Kafka `merchant_events`/`device_events` upserts converge to latest.
-- Static dims (dates/geography/payment_method/risk_level) are populated here
-- as Infrastructure-as-Code (TRUNCATE+INSERT so re-apply stays idempotent).
-- ============================================================

-- ---------- dim_merchants (SCD-1; sink for merchant_events) ----------
CREATE TABLE IF NOT EXISTS payments.dim_merchants
(
    merchant_id      LowCardinality(String),
    legal_name       String DEFAULT '',
    dba_name         String DEFAULT '',
    business_type    LowCardinality(String) DEFAULT '',
    mcc              LowCardinality(String) DEFAULT '',
    category         LowCardinality(String) DEFAULT '',
    city             LowCardinality(String) DEFAULT '',
    state            LowCardinality(String) DEFAULT '',
    pincode          FixedString(6) DEFAULT '000000',
    latitude         Float64 DEFAULT 0,
    longitude        Float64 DEFAULT 0,
    settlement_bank  LowCardinality(String) DEFAULT '',
    settlement_cycle LowCardinality(String) DEFAULT 'T+1',
    mdr_card_credit_bps UInt16 DEFAULT 0,
    mdr_upi_bps      UInt16 DEFAULT 0,
    device_count     UInt16 DEFAULT 0,
    avg_ticket       Float32 DEFAULT 0,
    risk_score       Float32 DEFAULT 0,
    risk_tier        LowCardinality(String) DEFAULT 'low',
    is_high_volume   UInt8 DEFAULT 0,
    onboarded_date   Date DEFAULT toDate('1970-01-01'),
    status           LowCardinality(String) DEFAULT 'active',
    event_time       String DEFAULT '',
    updated_at       DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY merchant_id;

-- ---------- dim_devices (SCD-1; sink for device_events) ----------
CREATE TABLE IF NOT EXISTS payments.dim_devices
(
    device_id        String,
    merchant_id      LowCardinality(String) DEFAULT '',
    terminal_id      FixedString(8) DEFAULT '00000000',
    terminal_type    LowCardinality(String) DEFAULT '',
    manufacturer     LowCardinality(String) DEFAULT '',
    model            LowCardinality(String) DEFAULT '',
    firmware_version LowCardinality(String) DEFAULT '',
    network_type     LowCardinality(String) DEFAULT '',
    status           LowCardinality(String) DEFAULT 'active',
    installed_date   Date DEFAULT toDate('1970-01-01'),
    updated_at       DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY device_id;

-- ---------- dim_customers (SCD-1) ----------
CREATE TABLE IF NOT EXISTS payments.dim_customers
(
    customer_id      String,
    age_band         LowCardinality(String) DEFAULT '',
    gender           LowCardinality(String) DEFAULT '',
    home_city        LowCardinality(String) DEFAULT '',
    home_state       LowCardinality(String) DEFAULT '',
    risk_profile     LowCardinality(String) DEFAULT 'low',
    preferred_method LowCardinality(String) DEFAULT '',
    kyc_level        LowCardinality(String) DEFAULT 'min',
    is_blacklisted   UInt8 DEFAULT 0,
    updated_at       DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY customer_id;

-- ---------- dim_dates (static calendar 2022-2027) ----------
CREATE TABLE IF NOT EXISTS payments.dim_dates
(
    date_key       Date,
    year           UInt16,
    quarter        UInt8,
    month          UInt8,
    month_name     LowCardinality(String),
    day            UInt8,
    day_of_week    UInt8,                 -- 1=Mon .. 7=Sun
    is_weekend     UInt8,
    is_month_start UInt8,
    is_month_end   UInt8,
    iso_week       UInt8
)
ENGINE = MergeTree ORDER BY date_key;

TRUNCATE TABLE payments.dim_dates;
INSERT INTO payments.dim_dates
SELECT
    d AS date_key,
    toYear(d), toQuarter(d), toMonth(d),
    formatDateTime(d, '%b'), toDayOfMonth(d), toDayOfWeek(d),
    toDayOfWeek(d) IN (6, 7),
    toDayOfMonth(d) = 1,
    d = toLastDayOfMonth(d),
    toISOWeek(d)
FROM (SELECT toDate('2022-01-01') + number AS d FROM numbers(2192));

-- ---------- dim_geography (static; platform cities) ----------
CREATE TABLE IF NOT EXISTS payments.dim_geography
(
    city       LowCardinality(String),
    state      LowCardinality(String),
    latitude   Float64,
    longitude  Float64,
    tier       UInt8
)
ENGINE = TinyLog;

TRUNCATE TABLE payments.dim_geography;
INSERT INTO payments.dim_geography VALUES ('Mumbai','Maharashtra',19.0760,72.8777,1),('Delhi','Delhi',28.7041,77.1025,1),('Bengaluru','Karnataka',12.9716,77.5946,1),('Hyderabad','Telangana',17.3850,78.4867,1),('Chennai','Tamil Nadu',13.0827,80.2707,1),('Pune','Maharashtra',18.5204,73.8567,1),('Kolkata','West Bengal',22.5726,88.3639,1),('Ahmedabad','Gujarat',23.0225,72.5714,2),('Jaipur','Rajasthan',26.9124,75.7873,2),('Lucknow','Uttar Pradesh',26.8467,80.9462,2),('Surat','Gujarat',21.1702,72.8311,2),('Indore','Madhya Pradesh',22.7196,75.8577,2),('Kochi','Kerala',9.9312,76.2673,2),('Chandigarh','Punjab',30.7333,76.7794,2),('Bhopal','Madhya Pradesh',23.2599,77.4126,3),('Nagpur','Maharashtra',21.1458,79.0882,3),('Coimbatore','Tamil Nadu',11.0168,76.9558,3),('Visakhapatnam','Andhra Pradesh',17.6868,83.2185,3);

-- ---------- dim_payment_method (static) ----------
CREATE TABLE IF NOT EXISTS payments.dim_payment_method
(
    method_code    LowCardinality(String),
    display_name   String,
    is_card        UInt8,
    settles_t_plus UInt8,
    mdr_bps_typical UInt16
)
ENGINE = TinyLog;

TRUNCATE TABLE payments.dim_payment_method;
INSERT INTO payments.dim_payment_method VALUES ('upi','UPI',0,1,0),('card','Card',1,1,180),('debit_card','Debit Card',1,1,40),('credit_card','Credit Card',1,2,180),('wallet','Wallet',0,1,150),('netbanking','Net Banking',0,1,90),('emi','EMI',1,2,220),('qr','QR',0,1,0);

-- ---------- dim_risk_level (static; fraud-score bands) ----------
CREATE TABLE IF NOT EXISTS payments.dim_risk_level
(
    risk_level LowCardinality(String),
    min_score  Float32,
    max_score  Float32,
    label      String,
    action     LowCardinality(String)
)
ENGINE = TinyLog;

TRUNCATE TABLE payments.dim_risk_level;
INSERT INTO payments.dim_risk_level VALUES ('low',0.0,0.30,'Low risk','allow'),('medium',0.30,0.60,'Monitor','allow_monitor'),('high',0.60,0.85,'Elevated','step_up'),('critical',0.85,1.01,'Critical','block');
