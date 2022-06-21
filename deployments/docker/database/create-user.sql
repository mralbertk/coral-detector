-- It is not ideal to have the PW in plain text. But:
-- 	(1) The app is intended for an isolated local environment
-- 	(2) The user has very limited privileges to reduce the risk
CREATE USER 'coral-detector'@'localhost' IDENTIFIED BY 'ilikecorals';
CREATE USER 'coral-detector'@'%' IDENTIFIED BY 'ilikecorals';
GRANT SELECT, INSERT, UPDATE ON coraldata.coralcoverage to 'coral-detector'@'localhost';
GRANT SELECT, INSERT, UPDATE ON coraldata.coralcoverage to 'coral-detector'@'%';