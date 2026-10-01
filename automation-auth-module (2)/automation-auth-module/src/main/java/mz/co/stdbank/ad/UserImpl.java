package mz.co.stdbank.ad;

import java.io.Serial;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import javax.naming.NamingEnumeration;
import javax.naming.NamingException;
import javax.naming.directory.Attribute;
import javax.naming.directory.Attributes;
import javax.naming.ldap.LdapName;
import javax.naming.ldap.Rdn;
import lombok.Getter;
import mz.co.stdbank.jactive.directory.User;
import org.springframework.context.annotation.Primary;

@Primary
public class UserImpl implements User {
  @Serial private static final long serialVersionUID = 400000000122L;
  @Getter private final String username;
  @Getter private final String firstName;
  @Getter private final String lastName;
  @Getter private final String email;
  private final List<String> groupsList = new ArrayList<>();
  private final List<String> tree = new ArrayList<>();
  @Getter private final String department;
  @Getter private final String badPasswordTime;
  @Getter private final String badPwdCount;

  public UserImpl(Attributes attr) throws NamingException {

    String givenName = getAttr(attr, "givenName");
    String name      = getAttr(attr, "name");

    this.firstName = (givenName != null ? givenName : (name != null ? name : ""));
    this.lastName  = getAttrOrDefault(attr, "sn", "");
    this.email     = getAttrOrDefault(attr, "userPrincipalName", getAttrOrDefault(attr, "mail", ""));
    this.username  = getAttrOrDefault(attr, "sAMAccountName", getAttrOrDefault(attr, "uid", ""));

    this.department      = getAttrOrDefault(attr, "department", "MZ Service Accounts");
    this.badPasswordTime = getAttrOrDefault(attr, "badPasswordTime", "0");
    this.badPwdCount     = getAttrOrDefault(attr, "badPwdCount", "0");

    Attribute distinguishedName = attr.get("distinguishedname");
    if (distinguishedName == null) {
      distinguishedName = attr.get("distinguishedName");
    }

    Attribute memberOf = attr.get("memberOf");

    if (memberOf != null) parseGroups(memberOf);
    if (distinguishedName != null) parseDn(distinguishedName);
  }

  private static String getAttr(Attributes attr, String key) throws NamingException {
    Attribute a = attr.get(key);
    if (a == null) return null;
    Object v = a.get();
    return v == null ? null : v.toString();
  }

  private static String getAttrOrDefault(Attributes attr, String key, String def) throws NamingException {
    String v = getAttr(attr, key);
    return (v == null || v.isBlank()) ? def : v;
  }

  private void parseDn(Attribute distinguishedName) throws NamingException {
    NamingEnumeration<?> dne = distinguishedName.getAll();
    if (dne.hasMore()) {
      String dn = dne.next().toString();
      LdapName ldapName = new LdapName(dn);
      Enumeration<String> all = ldapName.getAll();

      while (all.hasMoreElements()) {
        Rdn node = new Rdn((String) all.nextElement());
        String val = node.getValue().toString();
        this.tree.add(val);
      }
    }
  }

  private void parseGroups(Attribute memberOf) throws NamingException {
    NamingEnumeration<?> groups = memberOf.getAll();

    while (groups.hasMore()) {
      String name = groups.next().toString();
      LdapName ldapName = new LdapName(name);
      Rdn commonName = ldapName.getRdn(ldapName.size() - 1);
      String groupName = commonName.getValue().toString();
      this.groupsList.add(groupName);
    }
  }

  public List<String> getGroups() {
    return Collections.unmodifiableList(this.groupsList);
  }

  public List<String> getDnTree() {
    return Collections.unmodifiableList(this.tree);
  }

  public boolean isMemberOf(String group) {
    if (group != null && !group.isEmpty()) {
      return this.groupsList.contains(group);
    } else {
      throw new IllegalArgumentException("group name reference must not be null nor empty");
    }
  }

  public boolean belongsTo(String node) {
    if (node != null && !node.isEmpty()) {
      return this.tree.contains(node);
    } else {
      throw new IllegalArgumentException("node name reference must not be null nor empty");
    }
  }

  public String toString() {
    return String.format(
        "{username=%s,email=%s,firstName=%s,lastName=%s,groups=%d,badPasswordTime=%s,badPwdCount=%s}",
        this.username,
        this.email,
        this.firstName,
        this.lastName,
        this.groupsList.size(),
        this.badPasswordTime,
        this.badPwdCount);
  }
}
