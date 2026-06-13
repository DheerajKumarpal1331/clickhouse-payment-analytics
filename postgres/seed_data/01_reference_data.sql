-- ============================================================
-- Reference / lookup master data.
-- MUST load before any merchant (FK -> mcc) or card txn (FK -> bin).
-- All INSERTs are ON CONFLICT DO NOTHING so re-seeding is safe.
-- ============================================================

-- ---------- Merchant Category Codes ----------
INSERT INTO ref.merchant_category (mcc, category_name, segment, risk_weight) VALUES
    ('5411','Grocery Stores & Supermarkets','grocery',0.05),
    ('5812','Eating Places & Restaurants','restaurant',0.08),
    ('5912','Drug Stores & Pharmacies','pharmacy',0.04),
    ('5541','Service Stations (Fuel)','fuel',0.06),
    ('5999','Miscellaneous Retail','retail',0.12),
    ('5732','Electronics Stores','electronics',0.18),
    ('8062','Hospitals','hospital',0.05),
    ('5969','Direct Marketing / E-commerce','ecommerce',0.30),
    ('4111','Transportation / Travel','travel',0.15),
    ('8220','Colleges & Education','education',0.07)
ON CONFLICT (mcc) DO NOTHING;

-- ---------- Banks (issuers / acquirers) ----------
INSERT INTO ref.bank (bank_code, bank_name, is_issuer, is_acquirer, ifsc_prefix) VALUES
    ('HDFC','HDFC Bank',TRUE,TRUE,'HDFC'),
    ('ICICI','ICICI Bank',TRUE,TRUE,'ICIC'),
    ('SBI','State Bank of India',TRUE,TRUE,'SBIN'),
    ('AXIS','Axis Bank',TRUE,TRUE,'UTIB'),
    ('KOTAK','Kotak Mahindra Bank',TRUE,FALSE,'KKBK'),
    ('YES','Yes Bank',TRUE,TRUE,'YESB'),
    ('IDFC','IDFC First Bank',TRUE,FALSE,'IDFB'),
    ('PNB','Punjab National Bank',TRUE,FALSE,'PUNB'),
    ('BOB','Bank of Baroda',TRUE,FALSE,'BARB'),
    ('CITI','Citibank',TRUE,FALSE,'CITI')
ON CONFLICT (bank_code) DO NOTHING;

-- ---------- Card networks ----------
INSERT INTO ref.card_network (network_code, network_name, interchange_share) VALUES
    ('visa','Visa',0.70),
    ('mastercard','Mastercard',0.70),
    ('rupay','RuPay',0.60),
    ('amex','American Express',0.80)
ON CONFLICT (network_code) DO NOTHING;

-- ---------- Card BIN master (sample ranges per network) ----------
INSERT INTO ref.card_bin_master (bin, network_code, issuer_bank, card_type, card_tier, country) VALUES
    ('421323','visa','HDFC','credit','platinum','IN'),
    ('400123','visa','ICICI','debit','classic','IN'),
    ('453278','visa','AXIS','credit','gold','IN'),
    ('521478','mastercard','SBI','debit','classic','IN'),
    ('536123','mastercard','KOTAK','credit','platinum','IN'),
    ('549876','mastercard','YES','credit','gold','IN'),
    ('607432','rupay','SBI','debit','classic','IN'),
    ('608123','rupay','PNB','debit','classic','IN'),
    ('652876','rupay','BOB','credit','gold','IN'),
    ('371234','amex','CITI','credit','platinum','IN')
ON CONFLICT (bin) DO NOTHING;

-- ---------- Payment method dimension ----------
INSERT INTO ref.payment_method_dim (method_code, display_name, is_card, settles_t_plus) VALUES
    ('upi','UPI',FALSE,1),
    ('debit_card','Debit Card',TRUE,1),
    ('credit_card','Credit Card',TRUE,2),
    ('wallet','Wallet',FALSE,1),
    ('emi','EMI',TRUE,2),
    ('qr','QR',FALSE,1),
    ('netbanking','Net Banking',FALSE,1)
ON CONFLICT (method_code) DO NOTHING;

-- ---------- Terminal capabilities ----------
INSERT INTO ref.terminal_capabilities
    (terminal_type, supports_chip, supports_nfc, supports_swipe, supports_pin, max_contactless_amount) VALUES
    ('android_smartpos',TRUE,TRUE,TRUE,TRUE,5000),
    ('linux_pos',TRUE,TRUE,TRUE,TRUE,5000),
    ('mpos_dongle',TRUE,FALSE,TRUE,TRUE,2000),
    ('soundbox_qr',FALSE,FALSE,FALSE,FALSE,0),
    ('ecom_gateway',FALSE,FALSE,FALSE,FALSE,0)
ON CONFLICT (terminal_type) DO NOTHING;

-- ---------- Locations (tier-1/2/3 cities) ----------
INSERT INTO ref.location (city, state, pincode, latitude, longitude, tier) VALUES
    ('Mumbai','Maharashtra','400001',19.0760,72.8777,1),
    ('Delhi','Delhi','110001',28.7041,77.1025,1),
    ('Bengaluru','Karnataka','560001',12.9716,77.5946,1),
    ('Hyderabad','Telangana','500001',17.3850,78.4867,1),
    ('Chennai','Tamil Nadu','600001',13.0827,80.2707,1),
    ('Pune','Maharashtra','411001',18.5204,73.8567,1),
    ('Kolkata','West Bengal','700001',22.5726,88.3639,1),
    ('Ahmedabad','Gujarat','380001',23.0225,72.5714,2),
    ('Jaipur','Rajasthan','302001',26.9124,75.7873,2),
    ('Lucknow','Uttar Pradesh','226001',26.8467,80.9462,2),
    ('Surat','Gujarat','395003',21.1702,72.8311,2),
    ('Indore','Madhya Pradesh','452001',22.7196,75.8577,2),
    ('Kochi','Kerala','682001',9.9312,76.2673,2),
    ('Chandigarh','Punjab','160001',30.7333,76.7794,2),
    ('Bhopal','Madhya Pradesh','462001',23.2599,77.4126,3),
    ('Nagpur','Maharashtra','440001',21.1458,79.0882,3),
    ('Coimbatore','Tamil Nadu','641001',11.0168,76.9558,3),
    ('Visakhapatnam','Andhra Pradesh','530001',17.6868,83.2185,3)
ON CONFLICT (city, state, pincode) DO NOTHING;

-- ---------- A few fraud rules (Module 8 reference) ----------
INSERT INTO fraud.fraud_rules (rule_code, description, rule_type, expression, severity, action) VALUES
    ('VEL_5M_GT_10','>10 txns from one card in 5 min','velocity','count_5m > 10','high','hold'),
    ('CARD_TEST_DECLINES','>5 declines in 10 min, tiny amounts','velocity','decline_10m > 5 AND avg_amount < 50','high','block'),
    ('GEO_IMPOSSIBLE','Impossible travel between txns','geo','geo_speed_kmph > 900','critical','block'),
    ('TICKET_OVER_LIMIT','Amount exceeds merchant max ticket','amount','amount > merchant_max_ticket','medium','step_up'),
    ('NEW_DEVICE_HIGH_AMT','New device + high amount','device','device_age_days < 1 AND amount > 20000','medium','step_up')
ON CONFLICT (rule_code) DO NOTHING;
