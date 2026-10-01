package mz.co.standardbank.service.events.listeners;

import mz.co.standardbank.entity.security.Account;
import mz.co.standardbank.service.AccountsRepositoryService;
import mz.co.standardbank.service.events.AccountLoggedInEvent;
import org.jboss.logging.Logger;
import org.springframework.context.ApplicationListener;
import org.springframework.stereotype.Component;

@Component
public class AccountLoggedInListener implements ApplicationListener<AccountLoggedInEvent> {
  private static final Logger log = Logger.getLogger(AccountLoggedInListener.class);
  private final AccountsRepositoryService accountsRepositoryService;

  public AccountLoggedInListener(AccountsRepositoryService accountsRepositoryService) {
    this.accountsRepositoryService = accountsRepositoryService;
  }

  @Override
  public void onApplicationEvent(AccountLoggedInEvent event) {
    Account account = event.getAccount();
    String channel = event.getChannel();

    try {
      log.infof("Persisting auth into the Database. Account %s. Request Channel %s", account, channel);
      account.setLoginAttempts(0);

      accountsRepositoryService.save(account);
    } catch (Exception e) {
      log.errorf(
          "Suppressed error while attempting to persisting account into the Database . Account %s. Request Channel %s",
          account, channel);
    }
  }
}
