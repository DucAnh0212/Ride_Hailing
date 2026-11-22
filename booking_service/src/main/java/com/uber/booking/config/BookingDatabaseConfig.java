package com.uber.booking.config;

import org.springframework.boot.autoconfigure.jdbc.DataSourceProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Configuration
public class BookingDatabaseConfig {

    private static final Logger LOGGER = Logger.getLogger(BookingDatabaseConfig.class.getName());
    private static final Pattern DB_NAME_PATTERN = Pattern.compile("(?i)(?:^|;)databaseName=([^;]+)");

    @Bean
    public DataSource dataSource(DataSourceProperties properties) {
        ensureSqlServerDatabaseExists(properties.getUrl(), properties.getUsername(), properties.getPassword());
        return properties.initializeDataSourceBuilder().build();
    }

    private void ensureSqlServerDatabaseExists(String url, String username, String password) {
        if (url == null || !url.toLowerCase().startsWith("jdbc:sqlserver:")) {
            return;
        }
        Matcher matcher = DB_NAME_PATTERN.matcher(url);
        if (!matcher.find()) {
            return;
        }
        String dbName = matcher.group(1).trim();
        if (!dbName.matches("^[A-Za-z][A-Za-z0-9_]*$") || "master".equalsIgnoreCase(dbName)) {
            return;
        }
        String masterUrl = url.replaceFirst("(?i)databaseName=[^;]+", "databaseName=master");
        int maxRetries = 15;
        for (int attempt = 1; attempt <= maxRetries; attempt++) {
            try (Connection conn = DriverManager.getConnection(masterUrl, username, password);
                 Statement stmt = conn.createStatement()) {
                stmt.execute("IF DB_ID('" + dbName + "') IS NULL CREATE DATABASE [" + dbName + "]");
                LOGGER.info("NODE: Booking-Service | Ensured isolated SQL Server database: " + dbName);
                return;
            } catch (Exception ex) {
                LOGGER.warning("NODE: Booking-Service | Waiting for SQL Server (" + attempt + "/" + maxRetries + "): " + ex.getMessage());
                if (attempt == maxRetries) {
                    throw new IllegalStateException("Failed to initialize database " + dbName, ex);
                }
                try {
                    Thread.sleep(2000L);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for SQL Server", ie);
                }
            }
        }
    }
}
