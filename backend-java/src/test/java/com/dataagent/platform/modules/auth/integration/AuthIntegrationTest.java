package com.dataagent.platform.modules.auth.integration;

import com.dataagent.platform.DataAgentApplication;
import com.dataagent.platform.modules.auth.domain.dto.AuthRegisterDTO;
import com.dataagent.platform.modules.auth.domain.model.AuthUser;
import com.dataagent.platform.modules.auth.domain.model.RefreshTokenSessionState;
import com.dataagent.platform.modules.auth.domain.po.AuthLoginLogPO;
import com.dataagent.platform.modules.auth.mapper.AuthLoginLogMapper;
import com.dataagent.platform.modules.auth.mapper.AuthUserMapper;
import com.dataagent.platform.modules.auth.repository.AuthRepository;
import com.dataagent.platform.modules.auth.service.AuthTokenStoreService;
import com.dataagent.platform.modules.dataset.mapper.DatasetMapper;
import com.dataagent.platform.modules.dataset.mapper.DatasetMysqlConnMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(
        classes = DataAgentApplication.class,
        properties = {
                "spring.autoconfigure.exclude="
                        + "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,"
                        + "org.springframework.boot.autoconfigure.jdbc.DataSourceTransactionManagerAutoConfiguration",
                "dataset.crypto.aes-key-base64=MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
                "auth.session.refresh-token-cookie-secure=false",
                "auth.session.inactivity-timeout=48h"
        }
)
@AutoConfigureMockMvc
@Import(AuthIntegrationTest.AuthIntegrationTestConfig.class)
class AuthIntegrationTest {

    private static final String DEFAULT_AVATAR_URL =
            "https://xiaoce-zhiguang.oss-cn-shenzhen.aliyuncs.com/avatars/2012078239280226305-1768909576074.jpg";
    private static final String REFRESH_COOKIE_NAME = "data-analysis-agent-refresh-token";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private InMemoryIntegrationAuthRepository authRepository;

    @Autowired
    private InMemoryIntegrationAuthTokenStoreService authTokenStoreService;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @MockBean
    private AuthUserMapper authUserMapper;

    @MockBean
    private AuthLoginLogMapper authLoginLogMapper;

    @MockBean
    private DatasetMapper datasetMapper;

    @MockBean
    private DatasetMysqlConnMapper datasetMysqlConnMapper;

    @MockBean
    private StringRedisTemplate stringRedisTemplate;

    @BeforeEach
    void setUp() {
        authRepository.reset(passwordEncoder);
        authTokenStoreService.clear();
        reset(authLoginLogMapper);
    }

    @Test
    void registerRefreshLogoutFlowShouldRotateInvalidateTokensAndWriteLoginMetadata() throws Exception {
        AuthRegisterDTO request = new AuthRegisterDTO(
                "new-user",
                "Password@123",
                "new-user",
                "",
                "new-user@example.com",
                "13800000011",
                (short) 0,
                "integration test"
        );

        MvcResult registerResult = mockMvc.perform(post("/api/auth/register")
                        .header("X-Forwarded-For", "203.0.113.10, 10.0.0.1")
                        .header(HttpHeaders.USER_AGENT, "Integration/Register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsBytes(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.username").value("new-user"))
                .andExpect(jsonPath("$.data.avatarUrl").value(DEFAULT_AVATAR_URL))
                .andExpect(jsonPath("$.data.refreshToken").isEmpty())
                .andReturn();

        JsonNode registerData = bodyData(registerResult);
        String userId = registerData.get("userId").asText();
        String accessToken = registerData.get("accessToken").asText();
        Cookie refreshCookie = extractRefreshCookie(registerResult);

        IntegrationAuthUserRecord registeredUser = authRepository.findRecordByUserId(userId).orElseThrow();
        assertThat(registeredUser.lastLoginAt()).isNotNull();
        assertThat(registeredUser.lastLoginIp()).isEqualTo("203.0.113.10");
        assertThat(registeredUser.avatarUrl()).isEqualTo(DEFAULT_AVATAR_URL);

        ArgumentCaptor<AuthLoginLogPO> registerLogCaptor = ArgumentCaptor.forClass(AuthLoginLogPO.class);
        verify(authLoginLogMapper).insert(registerLogCaptor.capture());
        assertThat(registerLogCaptor.getValue().getUsername()).isEqualTo("new-user");
        assertThat(registerLogCaptor.getValue().getClientPublicIp()).isEqualTo("203.0.113.10");
        assertThat(registerLogCaptor.getValue().getUserAgent()).isEqualTo("Integration/Register");

        mockMvc.perform(get("/api/auth/me")
                        .header(HttpHeaders.AUTHORIZATION, bearer(accessToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.userId").value(userId))
                .andExpect(jsonPath("$.data.nickname").value("new-user"));

        MvcResult refreshResult = mockMvc.perform(post("/api/auth/refresh")
                        .cookie(refreshCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.refreshToken").isEmpty())
                .andReturn();

        JsonNode refreshData = bodyData(refreshResult);
        String rotatedAccessToken = refreshData.get("accessToken").asText();
        Cookie rotatedRefreshCookie = extractRefreshCookie(refreshResult);

        mockMvc.perform(post("/api/auth/refresh")
                        .cookie(refreshCookie))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value(401));

        mockMvc.perform(post("/api/auth/logout")
                        .header(HttpHeaders.AUTHORIZATION, bearer(rotatedAccessToken))
                        .cookie(rotatedRefreshCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.loggedOut").value(true));

        mockMvc.perform(get("/api/auth/me")
                        .header(HttpHeaders.AUTHORIZATION, bearer(rotatedAccessToken)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value(401));

        mockMvc.perform(post("/api/auth/refresh")
                        .cookie(rotatedRefreshCookie))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void refreshShouldRejectSessionAfterFortyEightHoursOfInactivity() throws Exception {
        MvcResult loginResult = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "username": "analyst01",
                                  "password": "Password@123"
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn();

        Cookie refreshCookie = extractRefreshCookie(loginResult);
        authTokenStoreService.rewindLastActivity("user-001", Duration.ofHours(49));

        mockMvc.perform(post("/api/auth/refresh")
                        .cookie(refreshCookie))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void loginShouldSupportEmailIdentifierAndWriteAuditLog() throws Exception {
        MvcResult result = mockMvc.perform(post("/api/auth/login")
                        .header("X-Real-IP", "198.51.100.20")
                        .header(HttpHeaders.USER_AGENT, "Integration/Login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "username": "analyst01@example.com",
                                  "password": "Password@123"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.userId").value("user-001"))
                .andExpect(jsonPath("$.data.roles[0]").value("ANALYST"))
                .andExpect(jsonPath("$.data.refreshToken").isEmpty())
                .andReturn();

        assertThat(extractRefreshCookie(result)).isNotNull();

        IntegrationAuthUserRecord user = authRepository.findRecordByUserId("user-001").orElseThrow();
        assertThat(user.lastLoginAt()).isNotNull();
        assertThat(user.lastLoginIp()).isEqualTo("198.51.100.20");

        ArgumentCaptor<AuthLoginLogPO> loginLogCaptor = ArgumentCaptor.forClass(AuthLoginLogPO.class);
        verify(authLoginLogMapper).insert(loginLogCaptor.capture());
        assertThat(loginLogCaptor.getValue().getUsername()).isEqualTo("analyst01");
        assertThat(loginLogCaptor.getValue().getClientPublicIp()).isEqualTo("198.51.100.20");
        assertThat(loginLogCaptor.getValue().getUserAgent()).isEqualTo("Integration/Login");
    }

    @Test
    void accessContextShouldIntersectRequestedDatasets() throws Exception {
        MvcResult loginResult = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "username": "analyst01",
                                  "password": "Password@123"
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn();

        String accessToken = bodyData(loginResult).get("accessToken").asText();

        mockMvc.perform(post("/api/auth/access-context")
                        .header(HttpHeaders.AUTHORIZATION, bearer(accessToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "datasetIds": ["dataset-sales", "dataset-ops"]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.userId").value("user-001"))
                .andExpect(jsonPath("$.data.allowedDatasets.length()").value(1))
                .andExpect(jsonPath("$.data.allowedDatasets[0]").value("dataset-sales"));
    }

    private JsonNode bodyData(MvcResult mvcResult) throws Exception {
        return objectMapper.readTree(mvcResult.getResponse().getContentAsByteArray()).get("data");
    }

    private String bearer(String accessToken) {
        return "Bearer " + accessToken;
    }

    private Cookie extractRefreshCookie(MvcResult mvcResult) {
        Cookie cookie = mvcResult.getResponse().getCookie(REFRESH_COOKIE_NAME);
        assertThat(cookie).isNotNull();
        return cookie;
    }

    @TestConfiguration
    static class AuthIntegrationTestConfig {

        @Bean
        InMemoryIntegrationAuthRepository inMemoryIntegrationAuthRepository(PasswordEncoder passwordEncoder) {
            InMemoryIntegrationAuthRepository repository = new InMemoryIntegrationAuthRepository();
            repository.reset(passwordEncoder);
            return repository;
        }

        @Bean
        @Primary
        AuthRepository authRepository(InMemoryIntegrationAuthRepository repository) {
            return repository;
        }

        @Bean
        InMemoryIntegrationAuthTokenStoreService inMemoryIntegrationAuthTokenStoreService() {
            return new InMemoryIntegrationAuthTokenStoreService();
        }

        @Bean
        @Primary
        AuthTokenStoreService authTokenStoreService(InMemoryIntegrationAuthTokenStoreService service) {
            return service;
        }
    }

    static class InMemoryIntegrationAuthRepository implements AuthRepository {

        private final AtomicLong idGenerator = new AtomicLong(1000L);
        private final Map<String, IntegrationAuthUserRecord> usersById = new ConcurrentHashMap<>();

        void reset(PasswordEncoder passwordEncoder) {
            usersById.clear();
            idGenerator.set(1000L);
            save(seedUser(
                    "user-001",
                    "analyst01",
                    passwordEncoder.encode("Password@123"),
                    "analyst",
                    "analyst01@example.com",
                    "13800000001",
                    Set.of("ANALYST"),
                    Set.of("dataset-sales", "dataset-finance"),
                    Set.of("phone")
            ));
            save(seedUser(
                    "user-002",
                    "admin01",
                    passwordEncoder.encode("Password@123"),
                    "admin",
                    "admin01@example.com",
                    "13800000002",
                    Set.of("ADMIN"),
                    Set.of("dataset-sales", "dataset-finance", "dataset-ops"),
                    Set.of("phone", "id_card")
            ));
        }

        @Override
        public Optional<AuthUser> findByIdentifier(String identifier) {
            String normalized = normalize(identifier);
            if (normalized == null) {
                return Optional.empty();
            }

            return usersById.values().stream()
                    .filter(user -> normalized.equalsIgnoreCase(user.username())
                            || normalized.equalsIgnoreCase(user.email())
                            || normalized.equalsIgnoreCase(user.phone()))
                    .findFirst()
                    .map(IntegrationAuthUserRecord::toDomain);
        }

        @Override
        public Optional<AuthUser> findByUsername(String username) {
            String normalized = normalize(username);
            if (normalized == null) {
                return Optional.empty();
            }

            return usersById.values().stream()
                    .filter(user -> normalized.equalsIgnoreCase(user.username()))
                    .findFirst()
                    .map(IntegrationAuthUserRecord::toDomain);
        }

        @Override
        public Optional<AuthUser> findByEmail(String email) {
            String normalized = normalize(email);
            if (normalized == null) {
                return Optional.empty();
            }

            return usersById.values().stream()
                    .filter(user -> normalized.equalsIgnoreCase(user.email()))
                    .findFirst()
                    .map(IntegrationAuthUserRecord::toDomain);
        }

        @Override
        public Optional<AuthUser> findByPhone(String phone) {
            String normalized = normalize(phone);
            if (normalized == null) {
                return Optional.empty();
            }

            return usersById.values().stream()
                    .filter(user -> normalized.equalsIgnoreCase(user.phone()))
                    .findFirst()
                    .map(IntegrationAuthUserRecord::toDomain);
        }

        @Override
        public Optional<AuthUser> findByUserId(String userId) {
            return Optional.ofNullable(usersById.get(normalize(userId)))
                    .map(IntegrationAuthUserRecord::toDomain);
        }

        Optional<IntegrationAuthUserRecord> findRecordByUserId(String userId) {
            return Optional.ofNullable(usersById.get(normalize(userId)));
        }

        @Override
        public AuthUser create(AuthRegisterDTO request, String passwordHash) {
            String userId = String.valueOf(idGenerator.incrementAndGet());
            IntegrationAuthUserRecord record = new IntegrationAuthUserRecord(
                    userId,
                    normalize(request.username()),
                    passwordHash,
                    normalize(request.nickname()),
                    normalizeNullable(request.avatarUrl()),
                    normalize(request.email()),
                    normalize(request.phone()),
                    request.gender() == null ? (short) 0 : request.gender(),
                    "ACTIVE",
                    "tenant-demo",
                    Set.of("ANALYST"),
                    Set.of("dataset-sales"),
                    Set.of("phone"),
                    null,
                    null
            );
            save(record);
            return record.toDomain();
        }

        @Override
        public void updateLoginSuccess(String userId, LocalDateTime loginAt, String loginIp) {
            findRecordByUserId(userId).ifPresent(record -> save(record.withLoginSuccess(loginAt, loginIp)));
        }

        private IntegrationAuthUserRecord seedUser(
                String userId,
                String username,
                String passwordHash,
                String nickname,
                String email,
                String phone,
                Set<String> roles,
                Set<String> allowedDatasets,
                Set<String> maskedColumns
        ) {
            return new IntegrationAuthUserRecord(
                    userId,
                    username,
                    passwordHash,
                    nickname,
                    "https://static.local/avatar/" + username + ".png",
                    email,
                    phone,
                    (short) 0,
                    "ACTIVE",
                    "tenant-demo",
                    roles,
                    allowedDatasets,
                    maskedColumns,
                    null,
                    null
            );
        }

        private void save(IntegrationAuthUserRecord user) {
            usersById.put(user.userId(), user);
        }

        private String normalize(String value) {
            if (value == null) {
                return null;
            }
            String normalized = value.trim();
            return normalized.isEmpty() ? null : normalized;
        }

        private String normalizeNullable(String value) {
            return normalize(value);
        }
    }

    record IntegrationAuthUserRecord(
            String userId,
            String username,
            String passwordHash,
            String nickname,
            String avatarUrl,
            String email,
            String phone,
            Short gender,
            String status,
            String tenantId,
            Set<String> roles,
            Set<String> allowedDatasets,
            Set<String> maskedColumns,
            LocalDateTime lastLoginAt,
            String lastLoginIp
    ) {

        AuthUser toDomain() {
            return new AuthUser(
                    userId,
                    username,
                    passwordHash,
                    nickname,
                    avatarUrl,
                    email,
                    phone,
                    gender,
                    status,
                    tenantId,
                    roles,
                    allowedDatasets,
                    maskedColumns
            );
        }

        IntegrationAuthUserRecord withLoginSuccess(LocalDateTime loginAt, String loginIp) {
            return new IntegrationAuthUserRecord(
                    userId,
                    username,
                    passwordHash,
                    nickname,
                    avatarUrl,
                    email,
                    phone,
                    gender,
                    status,
                    tenantId,
                    roles,
                    allowedDatasets,
                    maskedColumns,
                    loginAt,
                    loginIp
            );
        }
    }

    static class InMemoryIntegrationAuthTokenStoreService implements AuthTokenStoreService {

        private final Map<String, String> refreshTokens = new ConcurrentHashMap<>();
        private final Map<String, RefreshTokenSessionState> refreshTokenStates = new ConcurrentHashMap<>();
        private final Map<String, Duration> blacklistedAccessTokens = new ConcurrentHashMap<>();

        @Override
        public void storeRefreshToken(String userId, String refreshToken, Duration ttl, Instant lastActivityAt) {
            if (isBlank(userId) || isBlank(refreshToken) || invalidTtl(ttl) || lastActivityAt == null) {
                return;
            }
            refreshTokens.put(userId, refreshToken);
            refreshTokenStates.put(userId, new RefreshTokenSessionState(Instant.now().plus(ttl), lastActivityAt));
        }

        @Override
        public Optional<RefreshTokenSessionState> findRefreshTokenSession(String userId, String refreshToken) {
            if (!refreshToken.equals(refreshTokens.get(userId))) {
                return Optional.empty();
            }
            return Optional.ofNullable(refreshTokenStates.get(userId));
        }

        @Override
        public void removeRefreshToken(String userId) {
            refreshTokens.remove(userId);
            refreshTokenStates.remove(userId);
        }

        @Override
        public void blacklistAccessToken(String userId, String tokenId, Duration ttl) {
            if (isBlank(userId) || isBlank(tokenId) || invalidTtl(ttl)) {
                return;
            }
            blacklistedAccessTokens.put(userId + ":" + tokenId, ttl);
        }

        @Override
        public boolean isAccessTokenBlacklisted(String userId, String tokenId) {
            return blacklistedAccessTokens.containsKey(userId + ":" + tokenId);
        }

        void rewindLastActivity(String userId, Duration delta) {
            RefreshTokenSessionState state = refreshTokenStates.get(userId);
            if (state == null || delta == null || delta.isNegative()) {
                return;
            }

            refreshTokenStates.put(
                    userId,
                    new RefreshTokenSessionState(state.expiresAt(), state.lastActivityAt().minus(delta))
            );
        }

        void clear() {
            refreshTokens.clear();
            refreshTokenStates.clear();
            blacklistedAccessTokens.clear();
        }

        private boolean isBlank(String value) {
            return value == null || value.isBlank();
        }

        private boolean invalidTtl(Duration ttl) {
            return ttl == null || ttl.isZero() || ttl.isNegative();
        }
    }
}
