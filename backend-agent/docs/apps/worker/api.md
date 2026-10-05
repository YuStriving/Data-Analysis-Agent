# Python Worker 接口与事件文档

> 当前实现核对：`src/agent_backend/api/kafka/worker.py` 只构造 LLM registry
> 和数据分析图并打印启动信息。它没有 Kafka consumer、回调 API 或事件发布接口；
> 本文件只记录当前脚手架，不将历史建议描述为可用契约。

## 1. 当前行为

调用 `main()` 会尝试从环境构造 LLM registry 和数据分析图，然后打印图对象；运行需要
有效的模型配置。当前没有提供可消费任务的 Worker 命令入口或 Kafka consumer。

## 2. 尚未定义的契约

当前没有确认的 Kafka topic、消息格式、重试策略、Java 回调或事件输出契约。
这些能力实施前应按根目录 [Spec 协作约定](../../../../docs/spec/README.md)
确认需求，再补充对应接口文档。
