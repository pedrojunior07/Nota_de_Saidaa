package mz.co.standardbank.service;

import java.util.Optional;
import mz.co.standardbank.entity.security.Account;
import mz.co.standardbank.repo.security.AccountsRepository;
import org.springframework.stereotype.Service;

@Service
public class AccountsRepositoryService {

  private final AccountsRepository accountsRepository;

  public AccountsRepositoryService(AccountsRepository accountsRepository) {
    this.accountsRepository = accountsRepository;
  }

  public Optional<Account> findByUsernameOrEmail(String username, String email) {
    Optional<Account> opt = accountsRepository.findAccountByUsernameOrEmail(username, email);
    return opt;
  }

  public Optional<Account> findByUsername(String username) {
    Optional<Account> opt = accountsRepository.findAccountByUsername(username);
    return opt;
  }

  public Account save(Account accountObj) throws RuntimeException {
    Account account = accountsRepository.save(accountObj);
    return account;
  }
}
