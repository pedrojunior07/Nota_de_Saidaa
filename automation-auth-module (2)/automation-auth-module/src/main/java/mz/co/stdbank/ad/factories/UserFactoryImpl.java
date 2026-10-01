package mz.co.stdbank.ad.factories;

import javax.naming.NamingException;
import javax.naming.directory.Attributes;
import mz.co.stdbank.ad.UserImpl;
import mz.co.stdbank.jactive.directory.DomainException;
import mz.co.stdbank.jactive.directory.User;
import mz.co.stdbank.jactive.directory.UserFactory;

public class UserFactoryImpl implements UserFactory {
    public User createInstance(Attributes attributes) {
        try {
            return (User)new UserImpl(attributes);
        } catch (NamingException ex) {
            throw new DomainException("Failed to create DomainMember instance", ex);
        }
    }
}
