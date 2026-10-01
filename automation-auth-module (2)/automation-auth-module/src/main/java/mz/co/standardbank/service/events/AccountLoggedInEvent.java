package mz.co.standardbank.service.events;

import lombok.Getter;
import mz.co.standardbank.entity.security.Account;
import org.springframework.context.ApplicationEvent;

public class AccountLoggedInEvent extends ApplicationEvent {

    @Getter
    private Account account;

    @Getter
    private String channel;

    public AccountLoggedInEvent(Object source, Account account, String channel){
        super(source);
        this.account = account;
        this.channel = channel;
    }
}
