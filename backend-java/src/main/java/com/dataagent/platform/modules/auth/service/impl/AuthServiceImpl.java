package com.dataagent.platform.modules.auth.service.impl;

import com.dataagent.platform.common.security.AuthenticatedUserPrincipal;
import com.dataagent.platform.common.security.TaskAccessContext;
import com.dataagent.platform.common.web.ApiException;
import com.dataagent.platform.common.web.ApiStatusCode;
import com.dataagent.platform.modules.auth.config.AuthSessionProperties;
import com.dataagent.platform.modules.auth.domain.dto.AuthRegisterDTO;
import com.dataagent.platform.modules.auth.domain.dto.AuthRequestMetadata;
import com.dataagent.platform.modules.auth.domain.dto.CurrentUserResponse;
import com.dataagent.platform.modules.auth.domain.dto.LoginRequest;
import com.dataagent.platform.modules.auth.domain.dto.LogoutResponse;
import com.dataagent.platform.modules.auth.domain.model.AuthSession;
import com.dataagent.platform.modules.auth.domain.model.AuthUser;
import com.dataagent.platform.modules.auth.domain.model.JwtUserClaims;
import com.dataagent.platform.modules.auth.domain.model.RefreshTokenSessionState;
import com.dataagent.platform.modules.auth.domain.po.AuthLoginLogPO;
import com.dataagent.platform.modules.auth.mapper.AuthLoginLogMapper;
import com.dataagent.platform.modules.auth.repository.AuthRepository;
import com.dataagent.platform.modules.auth.service.AuthService;
import com.dataagent.platform.modules.auth.service.AuthTokenStoreService;
import com.dataagent.platform.modules.auth.service.JwtTokenService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private static final short GENDER_UNKNOWN = 0;
    private static final short GENDER_MALE = 1;
    private static final short GENDER_FEMALE = 2;
    private static final String DEFAULT_AVATAR_URL =
            "https://xiaoce-zhiguang.oss-cn-shenzhen.aliyuncs.com/avatars/2012078239280226305-1768909576074.jpg";
    private static final Pattern EMAIL_PATTERN = Pattern.compile("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
    private static final Pattern PHONE_PATTERN = Pattern.compile("^1[3-9]\\d{9}$");
    private static final Pattern SPECIAL_CHAR_PATTERN = Pattern.compile("[!@#$%^&*()_\\-+=\\[\\]{};:'\"\\\\|,.<>/?]");

    private final AuthRepository authRepository;
    private final AuthTokenStoreService authTokenStoreService;
    private final JwtTokenService jwtTokenService;
    private final PasswordEncoder passwordEncoder;
    private final AuthLoginLogMapper authLoginLogMapper;
    private final AuthSessionProperties authSessionProperties;

    @Override
    public AuthSession register(AuthRegisterDTO request, AuthRequestMetadata requestMetadata) {
        if (request == null) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "注册请求不能为空。");
        }

        String username = normalize(request.username());
        String password = request.password() == null ? "" : request.password();
        String nickname = normalize(request.nickname());
        String email = normalize(request.email());
        String phone = normalize(request.phone());
        String avatarUrl = defaultAvatarUrl(request.avatarUrl());
        Short gender = normalizeGender(request.gender());
        String remark = normalizeNullable(request.remark());

        if (isBlank(username) || isBlank(password) || isBlank(email) || isBlank(phone)) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "请完整填写注册信息。");
        }

        validateUsername(username);
        validateEmail(email);
        validatePhone(phone);
        validatePassword(password);

        if (authRepository.findByUsername(username).isPresent()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "用户名已存在，请更换后再试。");
        }

        if (authRepository.findByEmail(email).isPresent()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "邮箱已存在，请更换后再试。");
        }

        if (authRepository.findByPhone(phone).isPresent()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "手机号已存在，请更换后再试。");
        }

        AuthUser user = authRepository.create(
                new AuthRegisterDTO(
                        username,
                        password,
                        isBlank(nickname) ? username : nickname,
                        avatarUrl,
                        email,
                        phone,
                        gender,
                        remark
                ),
                passwordEncoder.encode(password)
        );

        LocalDateTime loginAt = LocalDateTime.now();
        recordLoginSuccess(user.userId(), requestMetadata, loginAt);
        recordLoginAudit(user, requestMetadata, loginAt);
        log.info("User registered successfully, userId={}", user.userId());
        return createPersistedSession(user, toInstant(loginAt));
    }

    @Override
    public Optional<AuthSession> login(LoginRequest request, AuthRequestMetadata requestMetadata) {
        if (request == null || isBlank(request.username()) || isBlank(request.password())) {
            log.warn("Login request rejected because username or password is blank");
            return Optional.empty();
        }

        String identifier = normalize(request.username());
        Optional<AuthUser> userOptional = authRepository.findByIdentifier(identifier);
        if (userOptional.isEmpty()) {
            log.warn("Login failed for identifier={}, reason=USER_NOT_FOUND", request.username());
            return Optional.empty();
        }

        AuthUser user = userOptional.orElseThrow();
        log.debug("Found user for login identifier={}", request.username());

        if (!passwordMatches(request.password(), user.passwordHash())) {
            log.warn("Login failed for identifier={}, reason=INVALID_PASSWORD", request.username());
            return Optional.empty();
        }

        if (!"ACTIVE".equalsIgnoreCase(user.status())) {
            String failureReason = "USER_STATUS_" + normalizeStatus(user.status());
            log.warn("Login failed for identifier={}, reason={}", request.username(), failureReason);
            return Optional.empty();
        }

        LocalDateTime loginAt = LocalDateTime.now();
        recordLoginSuccess(user.userId(), requestMetadata, loginAt);
        recordLoginAudit(user, requestMetadata, loginAt);
        AuthSession session = createPersistedSession(user, toInstant(loginAt));
        log.info("Login succeeded for userId={}", session.user().userId());
        return Optional.of(session);
    }

    @Override
    public LogoutResponse logout(String accessToken, String refreshToken) {
        if (!isBlank(accessToken)) {
            jwtTokenService.decodeAccessToken(accessToken).ifPresent(claims -> {
                authTokenStoreService.removeRefreshToken(claims.userId());
                authTokenStoreService.blacklistAccessToken(
                        claims.userId(),
                        claims.tokenId(),
                        durationUntil(claims.expiresAt())
                );
            });
        }

        if (!isBlank(refreshToken)) {
            jwtTokenService.decodeRefreshToken(refreshToken)
                    .ifPresent(claims -> authTokenStoreService.removeRefreshToken(claims.userId()));
        }

        log.info("Processed logout request");
        return new LogoutResponse(true);
    }

    @Override
    public Optional<AuthSession> refresh(String refreshToken, AuthRequestMetadata requestMetadata) {
        if (isBlank(refreshToken)) {
            log.warn("Refresh request rejected because refresh token cookie is blank");
            return Optional.empty();
        }

        Instant now = Instant.now();
        return jwtTokenService.decodeRefreshToken(refreshToken)
                .flatMap(claims -> validateRefreshSession(claims, refreshToken, now))
                .flatMap(claims -> authRepository.findByUserId(claims.userId()))
                .filter(user -> "ACTIVE".equalsIgnoreCase(user.status()))
                .map(user -> createPersistedSession(user, resolveRefreshActivityAt(requestMetadata, now)))
                .map(session -> {
                    log.info("Refresh token succeeded for userId={}", session.user().userId());
                    return session;
                })
                .or(() -> {
                    log.warn("Refresh token failed");
                    return Optional.empty();
                });
    }

    @Override
    public TaskAccessContext contextDemo() {
        return new TaskAccessContext(
                "tenant-demo",
                "user-demo",
                Set.of("ANALYST"),
                Set.of("dataset-sales"),
                Set.of("phone"),
                true
        );
    }

    @Override
    public Optional<AuthenticatedUserPrincipal> authenticate(String accessToken) {
        if (isBlank(accessToken)) {
            return Optional.empty();
        }

        return jwtTokenService.decodeAccessToken(accessToken)
                .filter(this::isAccessTokenUsable)
                .flatMap(claims -> buildPrincipal(accessToken, claims))
                .or(() -> {
                    log.debug("No user resolved from access token");
                    return Optional.empty();
                });
    }

    @Override
    public Optional<CurrentUserResponse> currentUser(String accessToken) {
        return authenticate(accessToken)
                .map(principal -> new CurrentUserResponse(
                        principal.userId(),
                        principal.username(),
                        principal.nickname(),
                        principal.avatarUrl(),
                        principal.status(),
                        principal.tenantId(),
                        principal.roles()
                ));
    }

    private Optional<AuthenticatedUserPrincipal> buildPrincipal(String accessToken, JwtUserClaims claims) {
        return authRepository.findByUserId(claims.userId())
                .filter(user -> "ACTIVE".equalsIgnoreCase(user.status()))
                .map(user -> new AuthenticatedUserPrincipal(
                        accessToken,
                        user.userId(),
                        claims.username(),
                        claims.nickname(),
                        claims.avatarUrl(),
                        claims.status(),
                        user.tenantId(),
                        user.roles(),
                        user.allowedDatasets(),
                        user.maskedColumns()
                ));
    }

    private AuthSession createPersistedSession(AuthUser user, Instant lastActivityAt) {
        AuthSession session = jwtTokenService.createSession(user);
        authTokenStoreService.storeRefreshToken(
                user.userId(),
                session.refreshToken(),
                Duration.ofSeconds(session.refreshTokenExpiresIn()),
                lastActivityAt
        );
        return session;
    }

    private Optional<JwtUserClaims> validateRefreshSession(JwtUserClaims claims, String refreshToken, Instant now) {
        Optional<RefreshTokenSessionState> sessionStateOptional = authTokenStoreService.findRefreshTokenSession(
                claims.userId(),
                refreshToken
        );
        if (sessionStateOptional.isEmpty()) {
            return Optional.empty();
        }

        RefreshTokenSessionState sessionState = sessionStateOptional.orElseThrow();
        if (sessionState.expiresAt() != null && now.isAfter(sessionState.expiresAt())) {
            authTokenStoreService.removeRefreshToken(claims.userId());
            log.info("Rejected expired refresh session for userId={}", claims.userId());
            return Optional.empty();
        }

        if (isInactiveTooLong(sessionState.lastActivityAt(), now)) {
            authTokenStoreService.removeRefreshToken(claims.userId());
            log.info("Rejected inactive refresh session for userId={}", claims.userId());
            return Optional.empty();
        }

        return Optional.of(claims);
    }

    private Instant resolveRefreshActivityAt(AuthRequestMetadata requestMetadata, Instant fallbackNow) {
        Instant candidate = requestMetadata == null ? null : requestMetadata.clientLastActivityAt();
        if (candidate == null) {
            return fallbackNow;
        }

        if (candidate.isAfter(fallbackNow.plusSeconds(60))) {
            return fallbackNow;
        }

        return candidate;
    }

    private boolean isInactiveTooLong(Instant lastActivityAt, Instant now) {
        if (lastActivityAt == null) {
            return true;
        }

        Duration inactiveDuration = Duration.between(lastActivityAt, now);
        return inactiveDuration.compareTo(authSessionProperties.getInactivityTimeout()) > 0;
    }

    private void recordLoginSuccess(String userId, AuthRequestMetadata requestMetadata, LocalDateTime loginAt) {
        if (isBlank(userId)) {
            return;
        }

        authRepository.updateLoginSuccess(
                userId,
                loginAt,
                normalizeNullable(requestMetadata == null ? null : requestMetadata.clientPublicIp())
        );
    }

    private void recordLoginAudit(AuthUser user, AuthRequestMetadata requestMetadata, LocalDateTime loginAt) {
        AuthLoginLogPO loginLog = new AuthLoginLogPO();
        loginLog.setUserId(parseLongOrNull(user.userId()));
        loginLog.setUsername(normalizeNullable(user.username()));
        loginLog.setClientPublicIp(normalizeNullable(requestMetadata == null ? null : requestMetadata.clientPublicIp()));
        loginLog.setUserAgent(normalizeNullable(requestMetadata == null ? null : requestMetadata.userAgent()));
        loginLog.setLoginAt(loginAt);
        authLoginLogMapper.insert(loginLog);
    }

    private boolean isAccessTokenUsable(JwtUserClaims claims) {
        boolean blacklisted = authTokenStoreService.isAccessTokenBlacklisted(claims.userId(), claims.tokenId());
        if (blacklisted) {
            log.info("Rejected blacklisted access token, userId={}, tokenId={}", claims.userId(), claims.tokenId());
            return false;
        }
        return true;
    }

    private Duration durationUntil(Instant expiresAt) {
        if (expiresAt == null) {
            return Duration.ZERO;
        }

        Duration duration = Duration.between(Instant.now(), expiresAt);
        return duration.isNegative() ? Duration.ZERO : duration;
    }

    private boolean passwordMatches(String rawPassword, String storedPasswordHash) {
        if (isBlank(storedPasswordHash)) {
            return false;
        }

        if (storedPasswordHash.startsWith("$2a$")
                || storedPasswordHash.startsWith("$2b$")
                || storedPasswordHash.startsWith("$2y$")) {
            return passwordEncoder.matches(rawPassword, storedPasswordHash);
        }

        return storedPasswordHash.equals(rawPassword);
    }

    private void validateUsername(String username) {
        if (username.length() < 3) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "用户名至少需要 3 个字符。");
        }
    }

    private void validateEmail(String email) {
        if (!EMAIL_PATTERN.matcher(email).matches()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "请输入常见格式的邮箱地址，例如 name@example.com。");
        }
    }

    private void validatePhone(String phone) {
        if (!PHONE_PATTERN.matcher(phone).matches()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "请输入 11 位中国大陆手机号。");
        }
    }

    private void validatePassword(String password) {
        if (password.length() < 8) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "密码至少需要 8 位。");
        }

        if (password.chars().noneMatch(Character::isLowerCase)) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "密码至少需要包含 1 个小写字母。");
        }

        if (password.chars().noneMatch(Character::isUpperCase)) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "密码至少需要包含 1 个大写字母。");
        }

        if (!SPECIAL_CHAR_PATTERN.matcher(password).find()) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "密码至少需要包含 1 个特殊字符。");
        }
    }

    private Short normalizeGender(Short gender) {
        if (gender == null) {
            return GENDER_UNKNOWN;
        }

        if (gender != GENDER_UNKNOWN && gender != GENDER_MALE && gender != GENDER_FEMALE) {
            throw new ApiException(ApiStatusCode.BAD_REQUEST, "gender 仅支持 0、1、2");
        }

        return gender;
    }

    private String normalize(String value) {
        return value == null ? null : value.trim();
    }

    private String normalizeNullable(String value) {
        String normalized = normalize(value);
        return isBlank(normalized) ? null : normalized;
    }

    private String defaultAvatarUrl(String avatarUrl) {
        String normalizedAvatarUrl = normalizeNullable(avatarUrl);
        return normalizedAvatarUrl == null ? DEFAULT_AVATAR_URL : normalizedAvatarUrl;
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private Long parseLongOrNull(String value) {
        String normalized = normalizeNullable(value);
        if (normalized == null) {
            return null;
        }

        try {
            return Long.valueOf(normalized);
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private String normalizeStatus(String status) {
        String normalized = normalizeNullable(status);
        return normalized == null ? "UNKNOWN" : normalized.toUpperCase();
    }

    private Instant toInstant(LocalDateTime localDateTime) {
        return localDateTime.atZone(ZoneId.systemDefault()).toInstant();
    }
}
