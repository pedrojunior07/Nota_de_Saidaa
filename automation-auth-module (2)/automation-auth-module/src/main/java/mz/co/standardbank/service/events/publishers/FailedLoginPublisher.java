package mz.co.standardbank.service.events.publishers;

import mz.co.standardbank.data.UserCredentials;
import mz.co.standardbank.service.events.FailedLoginEvent;
import mz.co.standardbank.service.events.listeners.FailedLoginListener;
import org.jboss.logging.Logger;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

@Component
public class FailedLoginPublisher {
  private static final Logger log = Logger.getLogger(FailedLoginListener.class);
  private final ApplicationEventPublisher applicationEventPublisher;

  public FailedLoginPublisher(ApplicationEventPublisher applicationEventPublisher) {
    this.applicationEventPublisher = applicationEventPublisher;
  }

  public void publish(UserCredentials userCredentials) {

    try {
      log.infof("Publishing Credentials to the  FailedLoginListener. Credentials %s", userCredentials);
      FailedLoginEvent event = new FailedLoginEvent(this, userCredentials);
      applicationEventPublisher.publishEvent(event);
    } catch (Exception e) {
      log.errorf(
          "An error prevented the publishing of FailedLoginEvent. FailedLoginEvent for credentials %s",
          userCredentials);
    }
  }
}
