package com.dataagent.platform.modules.dataset.domain.po;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

@Getter
@Setter
@ToString
@NoArgsConstructor
@TableName("dataset_mysql_conn")
public class DatasetMysqlConnPO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("dataset_id")
    private String datasetId;

    @TableField("host")
    private String host;

    @TableField("port")
    private Integer port;

    @TableField("database_name")
    private String databaseName;

    @TableField("username")
    private String username;

    @TableField("password_cipher")
    private String passwordCipher;

    @TableField("schema_json")
    private String schemaJson;

    @TableField("created_at")
    private LocalDateTime createdAt;

    @TableField("updated_at")
    private LocalDateTime updatedAt;
}
