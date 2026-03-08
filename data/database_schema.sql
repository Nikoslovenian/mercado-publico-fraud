PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE alerts (
	id INTEGER NOT NULL, 
	ocid VARCHAR, 
	alert_type VARCHAR, 
	severity VARCHAR, 
	title VARCHAR, 
	description TEXT, 
	evidence JSON, 
	buyer_rut VARCHAR, 
	buyer_name VARCHAR, 
	supplier_rut VARCHAR, 
	supplier_name VARCHAR, 
	region VARCHAR, 
	amount_involved FLOAT, 
	created_at DATETIME, 
	status VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ocid) REFERENCES procurements (ocid)
);
CREATE TABLE awards (
	id VARCHAR NOT NULL, 
	ocid VARCHAR, 
	supplier_rut VARCHAR, 
	supplier_name VARCHAR, 
	amount FLOAT, 
	currency VARCHAR, 
	date DATETIME, 
	status VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ocid) REFERENCES procurements (ocid)
);
CREATE TABLE bids (
	id VARCHAR NOT NULL, 
	ocid VARCHAR, 
	supplier_rut VARCHAR, 
	supplier_name VARCHAR, 
	amount FLOAT, 
	currency VARCHAR, 
	date DATETIME, 
	status VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ocid) REFERENCES procurements (ocid)
);
CREATE TABLE external_data (
	rut VARCHAR NOT NULL, 
	source VARCHAR NOT NULL, 
	raw_data JSON, 
	last_updated DATETIME, 
	PRIMARY KEY (rut, source)
);
CREATE TABLE items (
	id VARCHAR NOT NULL, 
	ocid VARCHAR, 
	award_id VARCHAR, 
	unspsc_code VARCHAR, 
	unspsc_prefix VARCHAR, 
	description VARCHAR, 
	quantity FLOAT, 
	unit VARCHAR, 
	unit_price FLOAT, 
	total_price FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ocid) REFERENCES procurements (ocid), 
	FOREIGN KEY(award_id) REFERENCES awards (id)
);
CREATE TABLE parties (
	rut VARCHAR NOT NULL, 
	name VARCHAR, 
	legal_name VARCHAR, 
	address VARCHAR, 
	region VARCHAR, 
	phone VARCHAR, 
	contact_name VARCHAR, 
	email VARCHAR, 
	party_type VARCHAR, 
	external_data_updated DATETIME, 
	sii_start_date DATETIME, 
	sii_activity_code VARCHAR, 
	sii_status VARCHAR, 
	is_public_employee BOOLEAN, 
	public_employee_org VARCHAR, 
	PRIMARY KEY (rut)
);
CREATE TABLE procurement_parties (
	id INTEGER NOT NULL, 
	procurement_ocid VARCHAR, 
	party_rut VARCHAR, 
	role VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(procurement_ocid) REFERENCES procurements (ocid), 
	FOREIGN KEY(party_rut) REFERENCES parties (rut)
);
CREATE TABLE procurements (
	ocid VARCHAR NOT NULL, 
	buyer_rut VARCHAR, 
	buyer_name VARCHAR, 
	region VARCHAR, 
	title VARCHAR, 
	description TEXT, 
	method VARCHAR, 
	method_details VARCHAR, 
	tender_start DATETIME, 
	tender_end DATETIME, 
	award_date DATETIME, 
	status VARCHAR, 
	total_amount FLOAT, 
	currency VARCHAR, 
	year INTEGER, 
	month INTEGER, 
	raw_file VARCHAR, 
	ingested_at DATETIME, 
	PRIMARY KEY (ocid)
);
CREATE INDEX ix_procurements_year ON procurements (year);
CREATE INDEX ix_procurements_method ON procurements (method);
CREATE INDEX idx_procurement_buyer_date ON procurements (buyer_rut, tender_start);
CREATE INDEX ix_procurements_region ON procurements (region);
CREATE INDEX ix_procurements_buyer_rut ON procurements (buyer_rut);
CREATE INDEX ix_procurements_status ON procurements (status);
CREATE INDEX ix_procurements_month ON procurements (month);
CREATE INDEX ix_parties_name ON parties (name);
CREATE INDEX ix_procurement_parties_party_rut ON procurement_parties (party_rut);
CREATE INDEX ix_procurement_parties_procurement_ocid ON procurement_parties (procurement_ocid);
CREATE INDEX ix_bids_supplier_rut ON bids (supplier_rut);
CREATE INDEX ix_bids_ocid ON bids (ocid);
CREATE INDEX idx_bids_supplier_ocid ON bids (supplier_rut, ocid);
CREATE INDEX ix_awards_supplier_rut ON awards (supplier_rut);
CREATE INDEX ix_awards_ocid ON awards (ocid);
CREATE INDEX idx_awards_supplier ON awards (supplier_rut, date);
CREATE INDEX ix_alerts_supplier_rut ON alerts (supplier_rut);
CREATE INDEX ix_alerts_alert_type ON alerts (alert_type);
CREATE INDEX idx_alerts_type_severity ON alerts (alert_type, severity);
CREATE INDEX ix_alerts_severity ON alerts (severity);
CREATE INDEX ix_alerts_region ON alerts (region);
CREATE INDEX ix_alerts_ocid ON alerts (ocid);
CREATE INDEX ix_alerts_buyer_rut ON alerts (buyer_rut);
CREATE INDEX idx_items_unspsc_price ON items (unspsc_prefix, unit_price);
CREATE INDEX ix_items_unspsc_prefix ON items (unspsc_prefix);
CREATE INDEX ix_items_ocid ON items (ocid);
CREATE INDEX ix_items_unspsc_code ON items (unspsc_code);
COMMIT;
