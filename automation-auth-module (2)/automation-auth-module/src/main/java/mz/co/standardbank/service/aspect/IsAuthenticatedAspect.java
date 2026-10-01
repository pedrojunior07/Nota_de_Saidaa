package mz.co.standardbank.service.aspect;

import jakarta.servlet.http.HttpServletRequest;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import mz.co.standardbank.entity.security.Account;
import mz.co.standardbank.exception.AuthenticationException;
import mz.co.standardbank.exception.AuthorizationException;
import mz.co.standardbank.holder.CallerPrincipalHolderImpl;
import mz.co.standardbank.repo.security.AccountsRepository;
import mz.co.standardbank.service.EncryptionServices;
import mz.co.standardbank.service.HashingServices;
import mz.co.standardbank.service.JWTServices;
import mz.co.standardbank.spec.IsAuthenticated;
import mz.co.standardbank.utils.HelperFactions;
import org.aspectj.lang.JoinPoint;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
import org.jboss.logging.Logger;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

@Aspect
@Component
public class IsAuthenticatedAspect {
  private static final Logger log = Logger.getLogger(IsAuthenticatedAspect.class);
  public final JWTServices jwtServices;
  public final EncryptionServices encryptionServices;
  public final HashingServices hashingServices;
  public final AccountsRepository accountsRepository;

  @Autowired private HttpServletRequest request;

  public IsAuthenticatedAspect(
      JWTServices jwtServices,
      EncryptionServices encryptionServices,
      HashingServices hashingServices,
      AccountsRepository accountsRepository) {

    this.jwtServices = jwtServices;
    this.encryptionServices = encryptionServices;
    this.hashingServices = hashingServices;
    this.accountsRepository = accountsRepository;
  }

  public static boolean containsCommonItem(List<String> list1, List<String> list2) {
    for (String item : list1) {
      if (list2.contains(item)) {
        return true;
      }
    }
    return false;
  }

  @Before("@annotation(isAuthenticated)")
  public void beforeAdvice(JoinPoint joinPoint, IsAuthenticated isAuthenticated) throws Exception {
    try {
      Account account;
      List groups = null;
      List dnTree = null;

      boolean belongsToGroup = false;
      boolean belongsDnTree = false;
      boolean checkPermissions = false;

      String authorization = getRequest("Authorization");
      String sessionKey = getRequest("Session-key");

      String groupsStr = isAuthenticated.groups();
      String dnTreeStr = isAuthenticated.dnTree();

      if (authorization != null && sessionKey != null) {
        account = authorizationVerifier(authorization, sessionKey);
        Optional<Account> found = accountsRepository.findAccountByUsername(account.getUsername());
        if (found.isPresent()) {
          account = found.get();
        } else {
          LocalDateTime time = LocalDateTime.now();
          account.setLastLoginDate(time);
          account = accountsRepository.save(account);
        }
        CallerPrincipalHolderImpl.setCurrentUser(account);
        request.setAttribute("account", account);
      } else {
        log.errorf("[Access denied] Invalid Token or Session-Key.");
        CallerPrincipalHolderImpl.clear();
        throw new AuthenticationException();
      }

      if (HelperFactions.strNotEmpty(groupsStr)) {
        checkPermissions = true;
        groups = HelperFactions.strToList(",", groupsStr);
        belongsToGroup = containsCommonItem(groups, account.getGroups());
      }

      if (HelperFactions.strNotEmpty(dnTreeStr)) {
        checkPermissions = true;
        dnTree = HelperFactions.strToList(",", dnTreeStr);
        belongsToGroup = containsCommonItem(dnTree, account.getDnTree());
      }

      if (checkPermissions && (!belongsToGroup && !belongsDnTree)) {
        log.errorf("[Access denied] User does not have the right access permissions.");
        CallerPrincipalHolderImpl.clear();
        throw new AuthorizationException();
      }

    } catch (Exception e) {
      log.errorf("An exception occurred while decrypting and verifying the Authorization token. ", e);
      CallerPrincipalHolderImpl.clear();
      throw new AuthenticationException();
    }
  }

  private String getRequest(String headerNAme) {
    HttpServletRequest request = ((ServletRequestAttributes) RequestContextHolder.getRequestAttributes()).getRequest();
    String header = request.getHeader(headerNAme);
    return header;
  }

  private Account authorizationVerifier(String token, String sessionKey) throws Exception {
    try {
      String hash = encryptionServices.decrypt(sessionKey);
      Boolean isMatch = hashingServices.compare(hash, token);
      if (!isMatch) {
        log.infof("Authorization Token does not match session-key");
        throw new AuthenticationException();
      }

      Account account = jwtServices.decodeAndVerifyJwt(token);
      return account;
    } catch (Exception e) {
      throw e;
    }
  }
}
