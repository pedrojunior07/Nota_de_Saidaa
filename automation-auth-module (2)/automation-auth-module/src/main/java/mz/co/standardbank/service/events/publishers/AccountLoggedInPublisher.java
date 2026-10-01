package mz.co.standardbank.service.events.publishers;

import mz.co.standardbank.entity.security.Account;
import mz.co.standardbank.holder.CallerPrincipalHolderImpl;
import mz.co.standardbank.service.events.AccountLoggedInEvent;
import mz.co.standardbank.spec.CallerPrincipalHolder;
import org.jboss.logging.Logger;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

@Component
public class AccountLoggedInPublisher {
  private static final Logger log = Logger.getLogger(AccountLoggedInPublisher.class);

  private final ApplicationEventPublisher applicationEventPublisher;

  public AccountLoggedInPublisher(ApplicationEventPublisher applicationEventPublisher) {
    this.applicationEventPublisher = applicationEventPublisher;
  }

  public void publish(Account account, String channel) {
    try {
      log.infof("Publishing Account and Channel to AccountLoggedInEvent. Account: %s, Channel %s", account, channel);
      AccountLoggedInEvent event = new AccountLoggedInEvent(this, account, channel);
      CallerPrincipalHolderImpl.setCurrentUser(account);
      applicationEventPublisher.publishEvent(event);
    } catch (Exception e) {
      log.errorf("Error publishing event will be suppressed. ", e);
    }
  }
}
