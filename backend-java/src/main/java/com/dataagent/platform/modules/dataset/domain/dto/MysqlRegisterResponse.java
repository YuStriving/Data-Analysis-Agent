package com.dataagent.platform.modules.dataset.domain.dto;

import java.util.List;

public record MysqlRegisterResponse(
        String datasetId,
        String sourceType,
        String status,
        List<String> tableNames
) {
}
