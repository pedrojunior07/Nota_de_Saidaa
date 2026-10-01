package mz.co.stdbank.jactive.directory;

import org.springframework.context.annotation.Primary;

import java.io.Serializable;
import java.util.List;

@Primary
public interface User extends Serializable {
    String getUsername();

    String getFirstName();

    String getLastName();

    String getEmail();

    List<String> getGroups();

    List<String> getDnTree();

    String getDepartment();

    String getBadPasswordTime();

    String getBadPwdCount();

    boolean isMemberOf(String var1);

    boolean belongsTo(String var1);
}
