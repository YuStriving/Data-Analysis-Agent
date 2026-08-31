package com.dataagent.platform.modules.dataset;

import com.dataagent.platform.common.web.ApiResponse;
import com.dataagent.platform.modules.dataset.domain.dto.MysqlRegisterRequest;
import com.dataagent.platform.modules.dataset.domain.dto.MysqlRegisterResponse;
import com.dataagent.platform.modules.dataset.domain.dto.UploadResultResponse;
import com.dataagent.platform.modules.dataset.service.DatasetService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/datasets")
public class DatasetController {
    private final DatasetService datasetService;

    @GetMapping("/demo")
    public ApiResponse<Map<String, Object>> demo() {
        return ApiResponse.ok(Map.of(
                "datasetId", "dataset-sales",
                "sourceType", "CSV",
                "status", "REGISTERED"
        ));
    }
    @PostMapping("/upload")
    public ApiResponse<UploadResultResponse> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam("datasetName") String datasetName,
            @RequestParam(value = "description", required = false) String description) {
        return ApiResponse.ok(datasetService.upload(file, datasetName, description));
    }

    @PostMapping("/mysql/register")
    public ApiResponse<MysqlRegisterResponse> registerMysql(
            @Valid @RequestBody MysqlRegisterRequest request) {
        return ApiResponse.ok(datasetService.registerMysql(request));
    }
}

