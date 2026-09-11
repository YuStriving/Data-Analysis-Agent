package com.dataagent.platform.common.security;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.security.Principal;
import java.util.Collection;
import java.util.Set;
import java.util.stream.Collectors;

public record AuthenticatedUserPrincipal(
        String accessToken,
        String userId,
        String username,
        String nickname,
        String avatarUrl,
        String status,
        String tenantId,
        Set<String> roles,
        Set<String> allowedDatasets,
        Set<String> maskedColumns
) implements Principal {

    @Override
    public String getName() {
        return username;
    }

    public Collection<? extends GrantedAuthority> authorities() {
        return roles.stream()
                .map(role -> new SimpleGrantedAuthority("ROLE_" + role))
                .collect(Collectors.toUnmodifiableSet());
    }

    public TaskAccessContext toTaskAccessContext(Set<String> requestedDatasetIds) {
        return new TaskAccessContext(
                tenantId,
                userId,
                roles,
                intersectDatasets(requestedDatasetIds),
                maskedColumns,
                true
        );
    }

    private Set<String> intersectDatasets(Set<String> requestedDatasetIds) {
        if (requestedDatasetIds == null || requestedDatasetIds.isEmpty()) {
            return allowedDatasets;
        }
        return requestedDatasetIds.stream()
                .filter(allowedDatasets::contains)
                .collect(Collectors.toUnmodifiableSet());
    }
}
