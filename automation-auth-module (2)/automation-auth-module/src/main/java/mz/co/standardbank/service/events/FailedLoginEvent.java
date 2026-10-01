package mz.co.standardbank.service.events;

import lombok.Getter;
import mz.co.standardbank.data.UserCredentials;
import org.springframework.context.ApplicationEvent;

public class FailedLoginEvent extends ApplicationEvent {

    @Getter
    private UserCredentials userCredentials;
    public FailedLoginEvent(Object source, UserCredentials userCredentials) {
        super(source);
        this.userCredentials = userCredentials;
    }
}
