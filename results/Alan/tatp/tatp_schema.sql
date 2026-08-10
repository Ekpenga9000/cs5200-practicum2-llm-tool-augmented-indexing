-- TATP (Telecom Application Transaction Processing) benchmark schema.
-- Postgres dialect. 4 tables. PK/FK only -- this is the no-extra-index baseline
-- state. subscriber columns are a representative subset of the full TATP spec
-- (s_id + sub_nbr alternate key + a few bit/hex/byte fields + msc/vlr location).

CREATE TABLE subscriber (
    s_id         INT PRIMARY KEY,
    sub_nbr      VARCHAR(15),      -- zero-padded s_id; alternate lookup key
    bit_1        SMALLINT,
    bit_2        SMALLINT,
    hex_1        SMALLINT,
    byte2_1      SMALLINT,
    msc_location INT,
    vlr_location INT
);

CREATE TABLE access_info (
    s_id    INT,
    ai_type SMALLINT,
    data1   SMALLINT,
    data2   SMALLINT,
    data3   VARCHAR(3),
    data4   VARCHAR(5),
    PRIMARY KEY (s_id, ai_type),
    FOREIGN KEY (s_id) REFERENCES subscriber(s_id)
);

CREATE TABLE special_facility (
    s_id        INT,
    sf_type     SMALLINT,
    is_active   SMALLINT,
    error_cntrl SMALLINT,
    data_a      SMALLINT,
    data_b      VARCHAR(5),
    PRIMARY KEY (s_id, sf_type),
    FOREIGN KEY (s_id) REFERENCES subscriber(s_id)
);

CREATE TABLE call_forwarding (
    s_id       INT,
    sf_type    SMALLINT,
    start_time SMALLINT,
    end_time   SMALLINT,
    numberx    VARCHAR(15),
    PRIMARY KEY (s_id, sf_type, start_time),
    FOREIGN KEY (s_id, sf_type) REFERENCES special_facility(s_id, sf_type)
);
