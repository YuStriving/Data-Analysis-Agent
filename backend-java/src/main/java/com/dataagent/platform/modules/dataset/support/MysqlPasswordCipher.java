package com.dataagent.platform.modules.dataset.support;

import org.springframework.stereotype.Component;

/**
 * 当前 MVP 阶段不启用数据源密码加密，避免本地启动依赖额外密钥配置。
 * 后续进入真实环境前，应替换为基于 KMS 或环境密钥的加密实现。
 */
@Component
public class MysqlPasswordCipher {

    public String encrypt(String plainText) {
        return plainText;
    }

    public String decrypt(String storedPassword) {
        return storedPassword;
    }
}
