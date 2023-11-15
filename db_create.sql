create DATABASE maxpatrol_vm;

CREATE TABLE info_systems (
    id SERIAL PRIMARY KEY,
    host VARCHAR(32) NOT NULL,
    os VARCHAR(32) DEFAULT 'Unknown Linux',
    version VARCHAR(32) DEFAULT 'Unknown',
    arch VARCHAR(32) DEFAULT 'Unknown'
);
