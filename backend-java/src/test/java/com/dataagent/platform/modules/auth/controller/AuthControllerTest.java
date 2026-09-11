package com.dataagent.platform.modules.auth.controller;

import com.dataagent.platform.common.security.AuthenticatedUserPrincipal;
import com.dataagent.platform.common.security.BearerTokenAuthenticationFilter;
import com.dataagent.platform.common.security.SecurityAccessContextHolder;
import com.dataagent.platform.common.security.SecurityAccessDeniedHandler;
import com.dataagent.platform.common.security.SecurityAuthenticationEntryPoint;
import com.dataagent.platform.common.security.SecurityConfig;
import com.dataagent.platform.common.security.TaskAccessContext;
import com.dataagent.platform.modules.auth.domain.dto.AuthRegisterDTO;
import com.dataagent.platform.modules.auth.domain.dto.AuthRequestMetadata;
import com.dataagent.platform.modules.auth.domain.dto.LoginRequest;
import com.dataagent.platform.modules.auth.domain.dto.LogoutResponse;
import com.dataagent.platform.modules.auth.domain.model.AuthSession;
import com.dataagent.platform.modules.auth.domain.model.AuthUser;
import com.dataagent.platform.modules.auth.service.AuthRefreshCookieService;
import com.dataagent.platform.modules.auth.service.AuthService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Optional;
import java.util.Set;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AuthController.class)
@Import({
        SecurityConfig.class,
        BearerTokenAuthenticationFilter.class,
        SecurityAuthenticationEntryPoint.class,
        SecurityAccessDeniedHandler.class
})
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private AuthService authService;

    @MockBean
    private AuthRefreshCookieService authRefreshCookieService;

    @MockBean
    private SecurityAccessContextHolder securityAccessContextHolder;

    @Test
    void registerShouldReturnTokenResponseAndPassRequestMetadata() throws Exception {
        AuthRegisterDTO request = new AuthRegisterDTO(
                "new-user",
                "Password@123",
                "new-user",
                "https://static.local/avatar/new-user.png",
                "new-user@example.com",
                "13800000011",
                (short) 0,
                "test register"
        );

        when(authService.register(eq(request), any(AuthRequestMetadata.class))).thenReturn(session());

        mockMvc.perform(post("/api/auth/register")
                        .header("X-Forwarded-For", "203.0.113.10, 10.0.0.1")
                        .header(HttpHeaders.USER_AGENT, "JUnit/Register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsBytes(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.accessToken").value("access-token"))
                .andExpect(jsonPath("$.data.refreshToken").isEmpty())
                .andExpect(jsonPath("$.data.userId").value("user-001"));

        verify(authService).register(eq(request), argThat(metadata ->
                "203.0.113.10".equals(metadata.clientPublicIp())
                        && "JUnit/Register".equals(metadata.userAgent())
                        && metadata.clientLastActivityAt() == null
        ));
        verify(authRefreshCookieService).writeRefreshTokenCookie(any(), eq("refresh-token"), eq(java.time.Duration.ofDays(7)));
    }

    @Test
    void loginShouldReturnUnauthorizedWhenCredentialsAreInvalid() throws Exception {
        LoginRequest request = new LoginRequest("analyst01", "wrong-password");

        when(authService.login(eq(request), any(AuthRequestMetadata.class))).thenReturn(Optional.empty());

        mockMvc.perform(post("/api/auth/login")
                        .header("X-Real-IP", "198.51.100.20")
                        .header(HttpHeaders.USER_AGENT, "JUnit/Login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsBytes(request)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value(401));

        verify(authService).login(eq(request), argThat(metadata ->
                "198.51.100.20".equals(metadata.clientPublicIp())
                        && "JUnit/Login".equals(metadata.userAgent())
                        && metadata.clientLastActivityAt() == null
        ));
    }

    @Test
    void refreshShouldReadTokenFromCookieAndReturnNewTokens() throws Exception {
        when(authRefreshCookieService.resolveRefreshToken(any())).thenReturn("refresh-token");
        when(authService.refresh(eq("refresh-token"), any(AuthRequestMetadata.class))).thenReturn(Optional.of(session()));

        mockMvc.perform(post("/api/auth/refresh"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.accessToken").value("access-token"))
                .andExpect(jsonPath("$.data.refreshToken").isEmpty());
    }

    @Test
    void meShouldReturnCurrentUserWhenBearerTokenIsValid() throws Exception {
        when(authService.authenticate("access-token")).thenReturn(Optional.of(principal()));

        mockMvc.perform(get("/api/auth/me")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer access-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.userId").value("user-001"))
                .andExpect(jsonPath("$.data.username").value("analyst01"))
                .andExpect(jsonPath("$.data.roles[0]").value("ANALYST"));
    }

    @Test
    void meShouldReturnUnauthorizedWithoutBearerToken() throws Exception {
        mockMvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void logoutShouldDeleteCurrentSessionWhenBearerTokenIsValid() throws Exception {
        when(authService.authenticate("access-token")).thenReturn(Optional.of(principal()));
        when(authRefreshCookieService.resolveRefreshToken(any())).thenReturn("refresh-token");
        when(authService.logout("access-token", "refresh-token")).thenReturn(new LogoutResponse(true));

        mockMvc.perform(post("/api/auth/logout")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer access-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.loggedOut").value(true));

        verify(authRefreshCookieService).clearRefreshTokenCookie(any());
    }

    @Test
    void accessContextShouldReturnScopedDatasets() throws Exception {
        TaskAccessContext accessContext = new TaskAccessContext(
                "tenant-demo",
                "user-001",
                Set.of("ANALYST"),
                Set.of("dataset-sales"),
                Set.of("phone"),
                true
        );

        when(authService.authenticate("access-token")).thenReturn(Optional.of(principal()));
        when(securityAccessContextHolder.currentTaskAccessContext(Set.of("dataset-sales"))).thenReturn(accessContext);

        mockMvc.perform(post("/api/auth/access-context")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer access-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "datasetIds": ["dataset-sales"]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.userId").value("user-001"))
                .andExpect(jsonPath("$.data.allowedDatasets[0]").value("dataset-sales"))
                .andExpect(jsonPath("$.data.readonly").value(true));

        verify(securityAccessContextHolder).currentTaskAccessContext(Set.of("dataset-sales"));
    }

    @Test
    void contextDemoShouldBeAccessibleWithoutAuthentication() throws Exception {
        TaskAccessContext accessContext = new TaskAccessContext(
                "tenant-demo",
                "user-demo",
                Set.of("ANALYST"),
                Set.of("dataset-sales"),
                Set.of("phone"),
                true
        );

        when(authService.contextDemo()).thenReturn(accessContext);

        mockMvc.perform(get("/api/auth/context-demo"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.userId").value("user-demo"));
    }

    private AuthSession session() {
        return new AuthSession(
                "access-token",
                "refresh-token",
                900L,
                604800L,
                new AuthUser(
                        "user-001",
                        "analyst01",
                        "encoded-password",
                        "analyst",
                        "https://static.local/avatar/analyst01.png",
                        "analyst01@example.com",
                        "13800000001",
                        (short) 0,
                        "ACTIVE",
                        "tenant-demo",
                        Set.of("ANALYST"),
                        Set.of("dataset-sales"),
                        Set.of("phone")
                )
        );
    }

    private AuthenticatedUserPrincipal principal() {
        return new AuthenticatedUserPrincipal(
                "access-token",
                "user-001",
                "analyst01",
                "analyst",
                "https://static.local/avatar/analyst01.png",
                "ACTIVE",
                "tenant-demo",
                Set.of("ANALYST"),
                Set.of("dataset-sales"),
                Set.of("phone")
        );
    }
}
