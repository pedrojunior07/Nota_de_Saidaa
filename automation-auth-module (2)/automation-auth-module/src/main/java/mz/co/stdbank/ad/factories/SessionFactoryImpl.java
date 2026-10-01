package mz.co.stdbank.ad.factories;


import mz.co.stdbank.ad.SessionImpl;
import mz.co.stdbank.jactive.directory.*;
import org.apache.commons.lang3.StringUtils;
import org.springframework.context.annotation.Primary;

import javax.naming.CommunicationException;
import javax.naming.NamingException;
import javax.naming.ldap.Control;
import javax.naming.ldap.InitialLdapContext;
import java.util.Hashtable;

@Primary
public class SessionFactoryImpl implements SessionFactory {
    public Session createSession(Domain domain, Credentials credentials) {
        return this.getSession(domain.getName(), credentials.getUsername(), credentials.getPassword(), (new ConnectionInfo.Builder()).build());
    }

    public Session createSession(Domain domain, Credentials credentials, ConnectionInfo connectionInfo) {
        return this.getSession(domain.getName(), credentials.getUsername(), credentials.getPassword(), connectionInfo);
    }

    private Session getSession(String domainName, String user, String pass, ConnectionInfo conn) {
        Hashtable<String, Object> props = new Hashtable();
        String principalName = user + "@" + domainName;
        props.put("java.naming.security.principal", principalName);
        props.put("java.naming.security.credentials", pass);
        String serverName = null;
        if (conn.isServerNameSet()) {
            serverName = conn.getServerName();
        }

        String ldapURL = "ldap://" + ((serverName == null || StringUtils.isEmpty(serverName)) ? domainName : serverName ) + (conn.isPortSet() ? String.format(":%d/", conn.getPort()) : "/");
        props.put("java.naming.factory.initial", "com.sun.jndi.ldap.LdapCtxFactory");
        props.put("java.naming.provider.url", ldapURL);
        props.put("java.naming.referral", "follow");

        try {
            return new SessionImpl(user, new InitialLdapContext(props, (Control[])null));
        } catch (CommunicationException ex) {
            throw new DomainException("Failed to connect to " + domainName + (serverName == null ? "" : " through " + serverName), ex);
        } catch (NamingException ex) {
            throw new DomainException("Failed to authenticate " + user + (serverName == null ? "" : " through " + serverName), ex);
        }
    }
}
