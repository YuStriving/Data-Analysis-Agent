package com.dataagent.platform.modules.dataset.service.impl;

import com.dataagent.platform.common.security.SecurityAccessContextHolder;
import com.dataagent.platform.common.storage.OssStorageService;
import com.dataagent.platform.modules.dataset.config.DatasetUploadProperties;
import com.dataagent.platform.modules.dataset.mapper.DatasetMapper;
import com.dataagent.platform.modules.dataset.mapper.DatasetMysqlConnMapper;
import com.dataagent.platform.modules.dataset.support.MysqlPasswordCipher;
import com.dataagent.platform.modules.dataset.support.MysqlSchemaInspector;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class DatasetServiceImplTest {

    @Mock
    private OssStorageService ossStorageService;

    @Mock
    private DatasetMapper datasetMapper;

    @Mock
    private DatasetMysqlConnMapper datasetMysqlConnMapper;

    @Mock
    private SecurityAccessContextHolder securityAccessContextHolder;

    @Mock
    private MysqlSchemaInspector mysqlSchemaInspector;

    @Mock
    private MysqlPasswordCipher mysqlPasswordCipher;

    @Test
    void uploadShouldRouteCsvXlsxAndXlsToConfiguredOssPrefixes() {
        assertUploadPrefix("sales.csv", "csv", "warehouse/csv");
        assertUploadPrefix("sales.xlsx", "xlsx", "warehouse/xlsx");
        assertUploadPrefix("sales.xls", "xls", "warehouse/xls");
    }

    private void assertUploadPrefix(String filename, String extension, String expectedPrefix) {
        DatasetServiceImpl service = new DatasetServiceImpl(
                ossStorageService,
                datasetMapper,
                datasetMysqlConnMapper,
                securityAccessContextHolder,
                mysqlSchemaInspector,
                mysqlPasswordCipher,
                new DatasetUploadProperties(Map.of(
                        "csv", "warehouse/csv",
                        "xlsx", "warehouse/xlsx",
                        "xls", "warehouse/xls"
                )),
                new ObjectMapper()
        );
        MockMultipartFile file = new MockMultipartFile("file", filename, "text/plain", "id,value\n1,10".getBytes());
        ArgumentCaptor<String> objectKeyCaptor = ArgumentCaptor.forClass(String.class);

        clearInvocations(ossStorageService);
        service.upload(file, "sales", "");

        verify(ossStorageService).upload(eq(file), objectKeyCaptor.capture());
        assertThat(objectKeyCaptor.getValue())
                .startsWith(expectedPrefix + "/")
                .endsWith("." + extension);
    }
}
