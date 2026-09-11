package com.dataagent.platform.common.security;

import java.util.Set;

public record TaskAccessContext(
        String tenantId,
        String userId,
        Set<String> roles,
        Set<String> allowedDatasets,
        Set<String> maskedColumns,
        boolean readonly
) {
}
