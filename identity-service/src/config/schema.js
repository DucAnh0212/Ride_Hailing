async function initializeSchema(pool) {
    await pool.request().query(`
        IF OBJECT_ID('dbo.Users', 'U') IS NULL
        CREATE TABLE dbo.Users (
            UserID INT IDENTITY(1,1) PRIMARY KEY,
            FullName NVARCHAR(100) NOT NULL,
            PhoneNumber VARCHAR(50) NOT NULL UNIQUE,
            PasswordHash VARCHAR(255) NULL,
            Role VARCHAR(20) NOT NULL CHECK (Role IN ('Rider', 'Driver')),
            CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
        );
        IF COL_LENGTH('dbo.Users', 'IsActive') IS NULL
            ALTER TABLE dbo.Users ADD IsActive BIT NOT NULL CONSTRAINT DF_Users_IsActive DEFAULT 1 WITH VALUES;
        IF OBJECT_ID('dbo.Vehicles', 'U') IS NULL
        CREATE TABLE dbo.Vehicles (
            VehicleID INT IDENTITY(1,1) PRIMARY KEY,
            DriverID INT NOT NULL REFERENCES dbo.Users(UserID),
            LicensePlate VARCHAR(50) NOT NULL UNIQUE,
            VehicleType VARCHAR(50) NOT NULL,
            Color NVARCHAR(30)
        );
    `);
}
module.exports = { initializeSchema };
