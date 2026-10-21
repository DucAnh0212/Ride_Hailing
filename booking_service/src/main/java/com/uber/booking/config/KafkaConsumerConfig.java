package com.uber.booking.config;

import org.apache.kafka.common.TopicPartition;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaOperations;
import org.springframework.kafka.listener.CommonErrorHandler;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

import java.util.logging.Logger;

@Configuration
public class KafkaConsumerConfig {

    private static final Logger LOGGER = Logger.getLogger(KafkaConsumerConfig.class.getName());

    @Bean
    public CommonErrorHandler errorHandler(KafkaOperations<Object, Object> template) {
        // Khi tin nhắn gặp lỗi xử lý, DeadLetterPublishingRecoverer sẽ đẩy sang topic .DLT tương ứng
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(template,
                (record, ex) -> {
                    LOGGER.warning(String.format("DeadLetterPublishingRecoverer: Đẩy tin nhắn lỗi sang topic %s.DLT. Lỗi: %s",
                            record.topic(), ex.getMessage()));
                    return new TopicPartition(record.topic() + ".DLT", record.partition());
                });

        // Thiết lập cơ chế Retry: Thử lại 3 lần, mỗi lần cách nhau 1000ms
        FixedBackOff backOff = new FixedBackOff(1000L, 3L);
        return new DefaultErrorHandler(recoverer, backOff);
    }
}
