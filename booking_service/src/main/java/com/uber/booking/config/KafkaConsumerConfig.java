package com.uber.booking.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.common.TopicPartition;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;
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
    public NewTopic tripRequestedTopic() { return TopicBuilder.name("trip.requested").partitions(1).replicas(1).build(); }

    @Bean
    public NewTopic driverMatchedTopic() { return TopicBuilder.name("driver.matched").partitions(1).replicas(1).build(); }

    @Bean
    public NewTopic matchingFailedTopic() { return TopicBuilder.name("matching.failed").partitions(1).replicas(1).build(); }

    @Bean
    public NewTopic tripAcceptedTopic() { return TopicBuilder.name("trip.accepted").partitions(1).replicas(1).build(); }

    @Bean
    public NewTopic tripRejectedTopic() { return TopicBuilder.name("trip.rejected").partitions(1).replicas(1).build(); }

    @Bean
    public NewTopic tripStartedTopic() { return TopicBuilder.name("trip.started").partitions(1).replicas(1).build(); }

    @Bean
    public NewTopic tripCompletedTopic() { return TopicBuilder.name("trip.completed").partitions(1).replicas(1).build(); }

    @Bean
    public NewTopic tripCancelledTopic() { return TopicBuilder.name("trip.cancelled").partitions(1).replicas(1).build(); }

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
