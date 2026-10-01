package mz.co.standardbank.service;

import lombok.RequiredArgsConstructor;
import mz.co.standardbank.data.UserCredentials;
import mz.co.standardbank.entity.security.AuthenticationLogs;
import mz.co.standardbank.repo.security.AuthenticationLogsRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.Date;

import static mz.co.standardbank.utils.HelperFactions.getSystemProperty;

@Service
@RequiredArgsConstructor
public class AuthenticationLogService {

    private final AuthenticationLogsRepository authenticationLogsRepository;

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void logException(UserCredentials userCredentials, Exception e, long start) {
        AuthenticationLogs log = new AuthenticationLogs();
        log.setUsername(userCredentials.getUsername());
        log.setLoginDate(new Date());
        log.setLoginDelay(System.currentTimeMillis() - start);
        log.setLoginException(e.getMessage());
        log.setLoginDns(getSystemProperty("active.directory.server.main", "mz.sbicdirectory.com"));
        authenticationLogsRepository.save(log);
    }
}
