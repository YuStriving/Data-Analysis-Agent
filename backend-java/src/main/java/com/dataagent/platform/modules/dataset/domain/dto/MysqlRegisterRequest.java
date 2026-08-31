package com.dataagent.platform.modules.dataset.domain.dto;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

public record MysqlRegisterRequest(
        @NotBlank(message = "数据集名称不能为空")
        @Size(max = 100, message = "数据集名称长度不能超过100")
        String datasetName,

        @NotBlank(message = "主机地址不能为空")
        String host,

        @NotNull(message = "端口号不能为空")
        Integer port,

        @NotBlank(message = "数据库名称不能为空")
        String database,

        @NotBlank(message = "用户名不能为空")
        String username,

        @NotBlank(message = "密码不能为空")
        String password,

        @Size(min = 1, message = "至少选择一个表")
        List<String> tableNames
) {}