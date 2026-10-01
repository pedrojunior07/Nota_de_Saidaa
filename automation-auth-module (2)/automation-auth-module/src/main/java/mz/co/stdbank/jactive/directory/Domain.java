package mz.co.stdbank.jactive.directory;

import java.util.Iterator;
import java.util.Optional;
import java.util.ServiceLoader;

public class Domain {
    private static UserFactory MEMBER_FACTORY;

    private static SessionFactory SESSION_FACTORY;

    static {
        load(UserFactory.class).ifPresent(factory -> MEMBER_FACTORY = factory);
        load(SessionFactory.class).ifPresent(factory -> SESSION_FACTORY = factory);
    }

    public static void setMemberFactory(UserFactory userFactory) {
        if (userFactory == null)
            throw new IllegalArgumentException("userFactory reference should not be null");
        MEMBER_FACTORY = userFactory;
    }

    public static void setSessionFactory(SessionFactory sessionFactory) {
        if (sessionFactory == null)
            throw new IllegalArgumentException("sessionFactory reference should not be null");
        SESSION_FACTORY = sessionFactory;
    }

    public static UserFactory getMemberFactory() {
        return MEMBER_FACTORY;
    }

    private static <ServiceType> Optional<ServiceType> load(Class<ServiceType> type) {
        ServiceLoader<ServiceType> loader = ServiceLoader.load(type);
        Iterator<ServiceType> iterator = loader.iterator();
        if (iterator.hasNext())
            return Optional.of(iterator.next());
        return Optional.empty();
    }

    private String name = null;

    public Domain(String name) {
        if (name == null || name.isEmpty())
            throw new IllegalArgumentException("domain name should not be null nor empty");
        this.name = name;
    }

    public Domain() {
        this.name = "mz.sbicdirectory.com";
    }

    private void checkRequirements() {
        if (MEMBER_FACTORY == null)
            throw new IllegalStateException("No UserFactory set!");
        if (SESSION_FACTORY == null)
            throw new IllegalStateException("No SessionFactory set!");
    }

    public Session getSession(Credentials credentials) {
        checkRequirements();
        return SESSION_FACTORY.createSession(this, credentials);
    }

    public Session getSession(Credentials credentials, ConnectionInfo info) {
        checkRequirements();
        return SESSION_FACTORY.createSession(this, credentials, info);
    }

    public String getName() {
        return this.name;
    }
}
