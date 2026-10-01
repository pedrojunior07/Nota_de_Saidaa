package mz.co.stdbank.jactive.directory;

import javax.naming.directory.Attributes;

public interface UserFactory {
    User createInstance(Attributes paramAttributes);
}
