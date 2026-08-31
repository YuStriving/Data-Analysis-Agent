package com.dataagent.platform.modules.dataset.service;

import com.dataagent.platform.modules.dataset.domain.dto.MysqlRegisterRequest;
import com.dataagent.platform.modules.dataset.domain.dto.MysqlRegisterResponse;
import com.dataagent.platform.modules.dataset.domain.dto.UploadResultResponse;
import org.springframework.web.multipart.MultipartFile;

public interface DatasetService {
    UploadResultResponse upload(MultipartFile file, String datasetName, String description);

    MysqlRegisterResponse registerMysql(MysqlRegisterRequest request);
}
