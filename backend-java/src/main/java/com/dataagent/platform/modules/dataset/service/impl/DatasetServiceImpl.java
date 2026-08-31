package com.dataagent.platform.modules.dataset.service.impl;

import com.dataagent.platform.common.security.AuthenticatedUserPrincipal;
import com.dataagent.platform.common.security.SecurityAccessContextHolder;
import com.dataagent.platform.common.storage.OssStorageService;
import com.dataagent.platform.common.web.ApiException;
import com.dataagent.platform.common.web.ApiStatusCode;
import com.dataagent.platform.modules.dataset.domain.dto.MysqlRegisterRequest;
import com.dataagent.platform.modules.dataset.domain.dto.MysqlRegisterResponse;
import com.dataagent.platform.modules.dataset.domain.dto.UploadResultResponse;
import com.dataagent.platform.modules.dataset.domain.po.DatasetMysqlConnPO;
import com.dataagent.platform.modules.dataset.domain.po.DatasetPO;
import com.dataagent.platform.modules.dataset.mapper.DatasetMapper;
import com.dataagent.platform.modules.dataset.mapper.DatasetMysqlConnMapper;
import com.dataagent.platform.modules.dataset.service.DatasetService;
import com.dataagent.platform.modules.dataset.support.MysqlPasswordCipher;
import com.dataagent.platform.modules.dataset.support.MysqlSchemaInspector;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
public class DatasetServiceImpl implements DatasetService {

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("csv", "xlsx", "xls");

    private final OssStorageService ossStorageService;
    private final DatasetMapper datasetMapper;
    private final DatasetMysqlConnMapper datasetMysqlConnMapper;
    private final SecurityAccessContextHolder securityAccessContextHolder;
    private final MysqlSchemaInspector mysqlSchemaInspector;
    private final MysqlPasswordCipher mysqlPasswordCipher;
    private final ObjectMapper objectMapper;

    public DatasetServiceImpl(OssStorageService ossStorageService,
                              DatasetMapper datasetMapper,
                              DatasetMysqlConnMapper datasetMysqlConnMapper,
                              SecurityAccessContextHolder securityAccessContextHolder,
                              MysqlSchemaInspector mysqlSchemaInspector,
                              MysqlPasswordCipher mysqlPasswordCipher,
                              ObjectMapper objectMapper) {
        this.ossStorageService = ossStorageService;
        this.datasetMapper = datasetMapper;
        this.datasetMysqlConnMapper = datasetMysqlConnMapper;
        this.securityAccessContextHolder = securityAccessContextHolder;
        this.mysqlSchemaInspector = mysqlSchemaInspector;
        this.mysqlPasswordCipher = mysqlPasswordCipher;
        this.objectMapper = objectMapper;
    }

    @Override
    public UploadResultResponse upload(MultipartFile file, String datasetName, String description) {
        if (file == null || file.isEmpty()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "上传文件不能为空");
        }
        if (datasetName == null || datasetName.isBlank()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "数据集名称不能为空");
        }

        String extension = extractExtension(file.getOriginalFilename());
        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "文件格式不支持，仅支持 csv / xlsx /xls");
        }

        String datasetId = "dataset-" + UUID.randomUUID().toString().substring(0, 8);
        String month = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy-MM"));
        String objectKey = "datasets/" + month + "/" + datasetId + "." + extension;
        ossStorageService.upload(file, objectKey);

        return new UploadResultResponse(datasetId, extension.toUpperCase(Locale.ROOT), "REGISTERING");
    }

    @Override
    @Transactional
    public MysqlRegisterResponse registerMysql(MysqlRegisterRequest request) {
        AuthenticatedUserPrincipal currentUser = securityAccessContextHolder.requireCurrentUser();

        Integer port = request.port();
        if (port == null || port < 1 || port > 65535) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "端口号必须在 1-65535 之间");
        }

        // 探测数据源：连通性测试 + 表存在性校验 + 读取表结构（任一失败直接抛错，不入库）
        Map<String, List<MysqlSchemaInspector.ColumnMeta>> schema = mysqlSchemaInspector.inspect(
                request.host(), port, request.database(),
                request.username(), request.password(), request.tableNames());

        String datasetId = "dataset-" + UUID.randomUUID().toString().substring(0, 8);
        LocalDateTime now = LocalDateTime.now();

        DatasetPO dataset = new DatasetPO();
        dataset.setDatasetId(datasetId);
        dataset.setName(request.datasetName());
        dataset.setSourceType("MYSQL");
        dataset.setStatus("REGISTERED");
        dataset.setOwnerUserId(currentUser.userId());
        dataset.setCreatedAt(now);
        dataset.setUpdatedAt(now);
        datasetMapper.insert(dataset);

        DatasetMysqlConnPO conn = new DatasetMysqlConnPO();
        conn.setDatasetId(datasetId);
        conn.setHost(request.host());
        conn.setPort(port);
        conn.setDatabaseName(request.database());
        conn.setUsername(request.username());
        conn.setPasswordCipher(mysqlPasswordCipher.encrypt(request.password()));
        conn.setSchemaJson(toJson(schema));
        conn.setCreatedAt(now);
        conn.setUpdatedAt(now);
        datasetMysqlConnMapper.insert(conn);

        return new MysqlRegisterResponse(datasetId, "MYSQL", "REGISTERED", List.copyOf(schema.keySet()));
    }

    private String toJson(Map<String, List<MysqlSchemaInspector.ColumnMeta>> schema) {
        try {
            return objectMapper.writeValueAsString(schema);
        } catch (Exception e) {
            throw new ApiException(ApiStatusCode.INTERNAL_SERVER_ERROR, "表结构序列化失败");
        }
    }

    private String extractExtension(String filename) {
        if (filename == null || !filename.contains(".")) {
            return "";
        }
        return filename.substring(filename.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }
}
