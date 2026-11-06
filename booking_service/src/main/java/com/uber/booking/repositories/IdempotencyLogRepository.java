package com.uber.booking.repositories;

import com.uber.booking.models.IdempotencyLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface IdempotencyLogRepository extends JpaRepository<IdempotencyLog, String> {
}
