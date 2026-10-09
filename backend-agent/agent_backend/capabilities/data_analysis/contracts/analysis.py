from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

GenerateSqlStatus = Literal["ok", "clarification_required", "cannot_generate"]
DatasetType = Literal["mysql", "csv", "xls", "xlsx"]
SqlDialect = Literal["mysql"]


class MysqlConnectionMetadata(BaseModel):
    sqlalchemy_url: str | None = None
    driver: str = "mysql+pymysql"
    username: str | None = None
    password: str | None = None
    host: str | None = None
    port: int = 3306
    database: str | None = None
    database_name: str | None = None
    query: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_connection_fields(self) -> MysqlConnectionMetadata:
        if self.sqlalchemy_url is not None and self.sqlalchemy_url.strip():
            return self
        missing_fields = [
            field_name
            for field_name, value in {
                "username": self.username,
                "password": self.password,
                "host": self.host,
                "database": self.database or self.database_name,
            }.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing_fields:
            raise ValueError(f"MySQL connection metadata is incomplete: {', '.join(missing_fields)}")
        return self

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MySQL port must be a positive integer")
        return value


class DatasetMetadata(BaseModel):
    dataset_id: str
    dataset_type: DatasetType
    display_name: str | None = None
    source: str | None = None
    schema_timeout_ms: int = 10000

    mysql: MysqlConnectionMetadata | None = None
    include_sample_values: bool = False
    sample_rows: int | None = None
    max_tables: int | None = None
    max_columns_per_table: int | None = None
    table_names: list[str] = Field(default_factory=list)

    file_ref: str | None = None
    local_path: str | None = None
    sheet_names: list[str] = Field(default_factory=list)
    header_row: int = 1
    max_rows_to_inspect: int = 1000

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("dataset_id is required")
        return value

    @field_validator("schema_timeout_ms", "max_rows_to_inspect")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("numeric metadata values must be positive")
        return value

    @field_validator("header_row")
    @classmethod
    def validate_header_row(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("header_row must be greater than 0")
        return value

    @field_validator("sample_rows", "max_tables", "max_columns_per_table")
    @classmethod
    def validate_optional_positive_int(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("optional numeric metadata values must be positive")
        return value

    @model_validator(mode="after")
    def validate_dataset_type_payload(self) -> DatasetMetadata:
        if self.dataset_type == "mysql":
            if self.mysql is None:
                raise ValueError("mysql metadata is required for mysql datasets")
            return self

        if not isinstance(self.file_ref, str) or not self.file_ref.strip():
            raise ValueError("file_ref is required for file datasets")
        if self.file_ref.startswith("oss://") and not _has_local_path(self.local_path):
            raise ValueError("local_path is required for oss file_ref in the MVP")
        return self

    def to_runtime_metadata(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude_none=True)


def validate_dataset_metadata(
    metadata: dict[str, Any],
    *,
    expected_dataset_id: str | None = None,
) -> DatasetMetadata:
    parsed = DatasetMetadata.model_validate(metadata)
    if expected_dataset_id is not None and parsed.dataset_id != expected_dataset_id:
        raise ValueError(f"Dataset metadata id mismatch: expected {expected_dataset_id}, got {parsed.dataset_id}")
    return parsed


def _has_local_path(value: str | None) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    return bool(Path(value))


class GenerateSqlResult(BaseModel):
    status: GenerateSqlStatus
    sql: str = ""
    sql_dialect: SqlDialect = "mysql"
    reason: str = ""
    used_tables: list[str] = Field(default_factory=list)
    used_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_payload(self) -> GenerateSqlResult:
        if self.status == "ok":
            if not self.sql.strip():
                raise ValueError("sql is required when status is ok")
            if not self.reason.strip():
                raise ValueError("reason is required when status is ok")
            if not self.used_tables:
                raise ValueError("used_tables is required when status is ok")
            if not self.used_fields:
                raise ValueError("used_fields is required when status is ok")
        if self.status == "clarification_required" and not self.clarification_questions:
            raise ValueError("clarification_questions is required when status is clarification_required")
        if self.status == "cannot_generate" and not self.reason.strip():
            raise ValueError("reason is required when status is cannot_generate")
        return self
