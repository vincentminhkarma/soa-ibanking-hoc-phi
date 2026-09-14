-- Database-per-service: mỗi service chỉ được truy cập database của chính nó.
-- Dùng chung một Postgres instance cho gọn môi trường demo; ranh giới dữ liệu
-- vẫn tách bạch vì không service nào biết connection string của service khác.
CREATE DATABASE authdb;
CREATE DATABASE accountdb;
CREATE DATABASE tuitiondb;
CREATE DATABASE paymentdb;
CREATE DATABASE otpdb;
CREATE DATABASE notificationdb;
