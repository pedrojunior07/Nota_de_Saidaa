package mz.co.standardbank.service.aspect;

import jakarta.servlet.http.HttpServletRequest;
import java.util.Date;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import mz.co.standardbank.entity.portal.UserActivity;
import mz.co.standardbank.entity.security.Account;
import mz.co.standardbank.repo.portal.UserActivityRepository;
import mz.co.standardbank.spec.*;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

@Aspect
@Component
@RequiredArgsConstructor
@Slf4j
public class LogActivityAspect {

  private final UserActivityRepository userActivityRepository;
  private final HttpServletRequest request;

  @Around("@annotation(logActivity)")
  public Object aroundAdvice(ProceedingJoinPoint pjp, LogActivity logActivity) throws Throwable {

    try {
      // 👉 Execute controller/service
      Object result = pjp.proceed();

      // 👉 Only log on SUCCESS
      saveActivity(logActivity);

      return result;

    } catch (Throwable ex) {
      // 👉 No log OR log as FAILED (your choice)
      throw ex; // VERY IMPORTANT: rethrow to trigger rollback
    }
  }

  private void saveActivity(LogActivity logActivity) {
    CallerPrincipalHolder holder = CallerPrincipalHolder.current();
    IAccount user = null;

    try {
      if (holder != null) {
        user = (Account) holder.getCurrentUser();
      }
    } catch (Exception e) {
      log.warn("CallerPrincipalHolder not found in current thread. Using system user.", e);
    }

    UserActivity ua = new UserActivity();
    ua.setActivity(logActivity.activity());
    ua.setAction(logActivity.action());
    ua.setUserName(user != null ? user.getUsername() : "backend_sys_user");
    ua.setActionDate(new Date());
    ua.setFromAddress(resolveClientIp());

    userActivityRepository.save(ua);
  }

  private String resolveClientIp() {
    String forwarded = request.getHeader("X-Forwarded-For");
    return forwarded != null ? forwarded.split(",")[0].trim() : request.getRemoteAddr();
  }
}
