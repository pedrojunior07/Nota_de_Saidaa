package mz.co.stdbank.jactive.directory;

import javax.naming.ldap.LdapContext;

public interface Session {
    LdapContext getContext();

    User getUser();

    void close();
}
