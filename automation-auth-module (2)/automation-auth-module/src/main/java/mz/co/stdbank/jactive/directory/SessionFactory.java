package mz.co.stdbank.jactive.directory;

public interface SessionFactory {
    Session createSession(Domain paramDomain, Credentials paramCredentials);

    Session createSession(Domain paramDomain, Credentials paramCredentials, ConnectionInfo paramConnectionInfo);
}
