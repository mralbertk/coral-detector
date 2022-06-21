CREATE DATABASE IF NOT EXISTS coraldata;

USE coraldata;

CREATE TABLE IF NOT EXISTS coralcoverage (
	island varchar(50) NOT NULL,
	year int NOT NULL,
	position int NOT NULL,
	coverage decimal(9,8) NOT NULL,
	last_update datetime NOT NULL,
	PRIMARY KEY (island, year, position)
);
