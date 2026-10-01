package mz.co.stdbank.ad;

import java.util.Optional;
import javax.naming.NamingEnumeration;
import javax.naming.NamingException;
import javax.naming.directory.Attributes;
import javax.naming.directory.SearchControls;
import javax.naming.directory.SearchResult;
import javax.naming.ldap.LdapContext;
import mz.co.stdbank.jactive.directory.*;
import org.springframework.context.annotation.Primary;

@Primary
public class SessionImpl implements Session {
  private final String[] desiredAttributes =
      new String[] {
        "distinguishedName",
        "cn",
        "name",
        "uid",
        "sn",
        "givenname",
        "memberOf",
        "samaccountname",
        "userPrincipalName",
        "subdivision",
        "Department",
        "badPasswordTime",
        "badPwdCount"
      };
  private final String username;
  private User cachedUser = null;
  private LdapContext ldapContext = null;

  public SessionImpl(String username, LdapContext ldapContext) {
    System.out.println(
            "SessionImpl loaded from: " +
                    SessionImpl.class
                            .getProtectionDomain()
                            .getCodeSource()
                            .getLocation()
    );
    this.ldapContext = ldapContext;
    this.username = username;
  }

  private static String toDC(String domainName) {
    StringBuilder buf = new StringBuilder();

    for (String token : domainName.split("\\.")) {
      if (!token.isEmpty()) {
        if (!buf.isEmpty()) {
          buf.append(",");
        }

        buf.append("DC=").append(token);
      }
    }

    return buf.toString();
  }

  public LdapContext getContext() {
    return this.ldapContext;
  }

  public User getUser() {
    if (this.cachedUser != null) {
      return this.cachedUser;
    } else {
      String q = String.format("(sAMAccountName=%s)", this.username);
      Optional<User> optional = this.getUserByQuery(q, this.ldapContext);
      if (optional.isEmpty()) {
        throw new UserNotFoundException("Failed to retrieve domain member details based in query : " + q);
      } else {
        this.cachedUser = (User) optional.get();
        return (User) optional.get();
      }
    }
  }

  public void close() {
    try {
      this.ldapContext.close();
    } catch (NamingException ex) {
      throw new DomainException("Failed to close ldapContext", ex);
    }
  }

  public Optional<User> getUserByQuery(String query, LdapContext context) {
    try {
      String domainName = null;
      String authenticatedUser = (String) context.getEnvironment().get("java.naming.security.principal");
      if (authenticatedUser.contains("@")) {
        domainName = authenticatedUser.substring(authenticatedUser.indexOf("@") + 1);
      }

      if (domainName != null) {
        SearchControls controls = new SearchControls();
        controls.setSearchScope(2);
        controls.setReturningAttributes(this.desiredAttributes);
        String name = toDC(domainName);
        NamingEnumeration<SearchResult> answer = context.search(name, "(& " + query + "(objectClass=user))", controls);
        if (answer.hasMore()) {
          Attributes attrs = ((SearchResult) answer.next()).getAttributes();
          return Optional.of(Domain.getMemberFactory().createInstance(attrs));
        }
      }
    } catch (NamingException ex) {
      throw new DomainException(String.format("Failed to find user by the supplied query: %s", query), ex);
    }

    return Optional.empty();
  }
}
