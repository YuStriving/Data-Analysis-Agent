package com.dataagent.platform.modules.dataset.support;

import com.dataagent.platform.common.web.ApiException;
import com.dataagent.platform.common.web.ApiStatusCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-GCM 加密组件，用于 MySQL 连接密码的加密存储。
 * 密文格式：Base64(12字节IV + 密文)，密钥来自配置 dataset.crypto.aes-key-base64（Base64 编码的 256 位密钥）。
 */
@Component
public class MysqlPasswordCipher {

    private static final String AES = "AES";
    private static final String GCM_NO_PADDING = "AES/GCM/NoPadding";
    private static final int IV_LENGTH = 12;
    private static final int TAG_LENGTH_BITS = 128;

    private final SecretKeySpec keySpec;
    private final SecureRandom secureRandom = new SecureRandom();

    public MysqlPasswordCipher(@Value("${dataset.crypto.aes-key-base64:}") String aesKeyBase64) {
        if (aesKeyBase64 == null || aesKeyBase64.isBlank()) {
            throw new IllegalStateException("缺少配置 dataset.crypto.aes-key-base64，请在 application.yml 或环境变量中提供 Base64 编码的 256 位 AES 密钥");
        }
        byte[] key = Base64.getDecoder().decode(aesKeyBase64.trim());
        if (key.length != 32) {
            throw new IllegalStateException("dataset.crypto.aes-key-base64 必须是 32 字节（256 位）的 Base64 编码密钥，当前为 " + key.length + " 字节");
        }
        this.keySpec = new SecretKeySpec(key, AES);
    }

    public String encrypt(String plainText) {
        try {
            byte[] iv = new byte[IV_LENGTH];
            secureRandom.nextBytes(iv);
            Cipher cipher = Cipher.getInstance(GCM_NO_PADDING);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, new GCMParameterSpec(TAG_LENGTH_BITS, iv));
            byte[] cipherText = cipher.doFinal(plainText.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            byte[] result = new byte[iv.length + cipherText.length];
            System.arraycopy(iv, 0, result, 0, iv.length);
            System.arraycopy(cipherText, 0, result, iv.length, cipherText.length);
            return Base64.getEncoder().encodeToString(result);
        } catch (Exception e) {
            throw new ApiException(ApiStatusCode.INTERNAL_SERVER_ERROR, "密码加密失败");
        }
    }

    public String decrypt(String cipherBase64) {
        try {
            byte[] decoded = Base64.getDecoder().decode(cipherBase64);
            byte[] iv = new byte[IV_LENGTH];
            System.arraycopy(decoded, 0, iv, 0, IV_LENGTH);
            Cipher cipher = Cipher.getInstance(GCM_NO_PADDING);
            cipher.init(Cipher.DECRYPT_MODE, keySpec, new GCMParameterSpec(TAG_LENGTH_BITS, iv));
            byte[] plainText = cipher.doFinal(decoded, IV_LENGTH, decoded.length - IV_LENGTH);
            return new String(plainText, java.nio.charset.StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new ApiException(ApiStatusCode.INTERNAL_SERVER_ERROR, "密码解密失败");
        }
    }
}
