package com.dataagent.platform.modules.dataset.support;

import com.dataagent.platform.common.web.ApiException;
import com.dataagent.platform.common.web.ApiStatusCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;

/**
 * MySQL 数据源探测组件：连通性测试、表存在性校验、读取表结构元数据。
 * 只对 information_schema 执行只读查询，不对用户库做任何写操作。
 */
@Component
public class MysqlSchemaInspector {

    /** MySQL 错误码：用户名或密码错误 */
    private static final int ER_ACCESS_DENIED_ERROR = 1045;
    /** MySQL 错误码：数据库不存在 */
    private static final int ER_BAD_DB_ERROR = 1049;

    private final int connectTimeoutMs;
    private final int socketTimeoutMs;

    public MysqlSchemaInspector(
            @Value("${dataset.mysql.connect-timeout-ms:5000}") int connectTimeoutMs,
            @Value("${dataset.mysql.socket-timeout-ms:10000}") int socketTimeoutMs) {
        this.connectTimeoutMs = connectTimeoutMs;
        this.socketTimeoutMs = socketTimeoutMs;
    }

    /**
     * 列结构元数据
     */
    public record ColumnMeta(String name, String type, String comment) {
    }

    /**
     * 探测结果：按表名分组的列信息（保持表顺序）
     */
    public Map<String, List<ColumnMeta>> inspect(String host, int port, String database,
                                                 String username, String password,
                                                 List<String> tableNames) {
        String url = buildJdbcUrl(host, port, database);
        Properties props = new Properties();
        props.setProperty("user", username);
        props.setProperty("password", password);
        props.setProperty("connectTimeout", String.valueOf(connectTimeoutMs));
        props.setProperty("socketTimeout", String.valueOf(socketTimeoutMs));

        try (Connection connection = DriverManager.getConnection(url, props)) {
            validateTables(connection, database, tableNames);
            return readColumns(connection, database, tableNames);
        } catch (SQLException e) {
            throw translateException(e);
        }
    }

    private String buildJdbcUrl(String host, int port, String database) {
        return "jdbc:mysql://" + host + ":" + port + "/" + database
                + "?useUnicode=true&characterEncoding=utf8"
                + "&serverTimezone=Asia/Shanghai"
                + "&useSSL=false"
                + "&allowPublicKeyRetrieval=true"
                + "&allowLoadLocalInfile=false";
    }

    private void validateTables(Connection connection, String database, List<String> tableNames) throws SQLException {
        String sql = "SELECT table_name FROM information_schema.tables "
                + "WHERE table_schema = ? AND table_name = ?";
        List<String> missing = new ArrayList<>();
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            for (String tableName : tableNames) {
                ps.setString(1, database);
                ps.setString(2, tableName);
                try (ResultSet rs = ps.executeQuery()) {
                    if (!rs.next()) {
                        missing.add(tableName);
                    }
                }
            }
        }
        if (!missing.isEmpty()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "以下表在目标数据库中不存在: " + String.join(", ", missing));
        }
    }

    private Map<String, List<ColumnMeta>> readColumns(Connection connection, String database,
                                                      List<String> tableNames) throws SQLException {
        String sql = "SELECT table_name, column_name, data_type, column_comment "
                + "FROM information_schema.columns "
                + "WHERE table_schema = ? AND table_name = ? "
                + "ORDER BY ordinal_position";
        Map<String, List<ColumnMeta>> schema = new LinkedHashMap<>();
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            for (String tableName : tableNames) {
                ps.setString(1, database);
                ps.setString(2, tableName);
                List<ColumnMeta> columns = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        columns.add(new ColumnMeta(
                                rs.getString("column_name"),
                                rs.getString("data_type"),
                                rs.getString("column_comment")));
                    }
                }
                schema.put(tableName, columns);
            }
        }
        return schema;
    }

    private ApiException translateException(SQLException e) {
        if (e.getErrorCode() == ER_ACCESS_DENIED_ERROR) {
            return new ApiException(ApiStatusCode.BAD_REQUEST, "MySQL 用户名或密码错误");
        }
        if (e.getErrorCode() == ER_BAD_DB_ERROR) {
            return new ApiException(ApiStatusCode.BAD_REQUEST, "目标数据库不存在");
        }
        return new ApiException(ApiStatusCode.BAD_REQUEST,
                "无法连接到 MySQL 数据源: " + e.getMessage());
    }
}
