package mz.co.standardbank.service.events.listeners;

import java.time.LocalDateTime;
import java.util.Optional;

import mz.co.standardbank.config.CustomPropertySourceFactory;
import mz.co.standardbank.data.UserCredentials;
import mz.co.standardbank.entity.security.Account;
import mz.co.standardbank.service.AccountsRepositoryService;
import mz.co.standardbank.service.events.FailedLoginEvent;
import org.jboss.logging.Logger;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationListener;
import org.springframework.context.annotation.PropertySource;
import org.springframework.stereotype.Component;

@Component
@PropertySource(
        value = "classpath:auth.properties",
        factory = CustomPropertySourceFactory.class
)
public class FailedLoginListener implements ApplicationListener<FailedLoginEvent> {
  private static final Logger log = Logger.getLogger(FailedLoginListener.class);

  @Value("${config.verifier.max-attempts}")
  private Integer maxLoginAttempts;

  @Value("${config.login.lock-time}")
  private Integer lockMinutes;

  private final AccountsRepositoryService accountsRepositoryService;

  public FailedLoginListener(AccountsRepositoryService accountsRepositoryService) {
    this.accountsRepositoryService = accountsRepositoryService;
  }

  @Override
  public void onApplicationEvent(FailedLoginEvent event) {
    UserCredentials userCredentials = event.getUserCredentials();
    try {
      log.infof("Failed Login attempt Registered. Credentials %s", userCredentials);
      Optional<Account> opt =
          accountsRepositoryService.findByUsernameOrEmail(userCredentials.getUsername().toUpperCase(), null);

      if (opt.isEmpty()) {
        log.infof(
            "Account not registered in the Database, no further action can be done at this point. Credentials %s",
            userCredentials);
        return;
      }
      ;

      LocalDateTime now = LocalDateTime.now();
      Account account = opt.get();
      account.setLoginAttempts(account.getLoginAttempts() + 1);

      if (account.getLockedUntil() != null) {
        if (now.isBefore(account.getLockedUntil()))
          log.infof(
              "Account is temporarily locked, no further action can be done at this point. Credentials %s",
              userCredentials);
      }

      if (account.getLoginAttempts() >= maxLoginAttempts) {
        log.infof(
            "Performing temporary lock on the account due to multiple failed login attempts. Credentials %s",
            userCredentials);
        LocalDateTime lockUntil = now.plusMinutes(lockMinutes);
        account.setLockedUntil(lockUntil);
        account.setLoginAttempts(0);
      }
      log.infof("Got here %s", account);
      accountsRepositoryService.save(account);

    } catch (Exception e) {
      log.errorf(
          "An error occurred while handling failed login attempt. Error will be suppressed. Credentials %s",
          userCredentials, e);
    }
  }
}
