package com.dataagent.platform.modules.dataset.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Locale;
import java.util.Map;

@ConfigurationProperties(prefix = "storage.oss")
public record DatasetUploadProperties(Map<String, String> uploadPrefixes) {

    private static final Map<String, String> DEFAULT_OSS_PREFIXES = Map.of(
            "csv", "datasets/csv",
            "xlsx", "datasets/xlsx",
            "xls", "datasets/xls"
    );

    public String ossPrefixFor(String extension) {
        String normalizedExtension = extension.toLowerCase(Locale.ROOT);
        String configuredPrefix = uploadPrefixes == null ? null : uploadPrefixes.get(normalizedExtension);
        String prefix = configuredPrefix == null || configuredPrefix.isBlank()
                ? DEFAULT_OSS_PREFIXES.get(normalizedExtension)
                : configuredPrefix;
        if (prefix == null || prefix.isBlank()) {
            return "datasets/" + normalizedExtension;
        }
        return trimSlashes(prefix);
    }

    private String trimSlashes(String value) {
        String trimmed = value.trim();
        while (trimmed.startsWith("/")) {
            trimmed = trimmed.substring(1);
        }
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }
}
