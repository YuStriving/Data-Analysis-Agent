# Infra

本目录管理本地依赖与部署配置。安全底线见 [根 AGENTS.md](../AGENTS.md)：
不得提交真实密钥、默认公开数据库或消息代理，清理或生产操作必须有明确目标。

- `docker/`：本地依赖编排；`mysql/`：数据库初始化资料；`redis/`、`kafka/`：
  运行依赖资料；`observability/`：观测配置；`k8s/`：后续部署占位或配置。
- 变更依赖时记录使用方、用途、端口与启动顺序；本地与生产配置明确分开。
  当前配置以 [docker-compose](docker/docker-compose.yml) 等实际文件为准。
- 修改配置后做受影响服务的配置校验和最小启动验证，方案与结果写入
  适用的 [quality Skill](../skills/quality/README.md)；单次结果记入 Plan 或交付说明。
