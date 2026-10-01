package mz.co.stdbank.jactive.directory;

public class Credentials {
    private String username;

    private String password;

    public Credentials(String username, String password) {
        if (username == null || username.isEmpty())
            throw new IllegalArgumentException("username must not be null nor empty");
        if (password == null || password.isEmpty())
            throw new IllegalArgumentException("password must not be null nor empty");
        this.username = username;
        this.password = password;
    }

    public static Credentials make(String username, String password) {
        return new Credentials(username, password);
    }

    public String getUsername() {
        return this.username;
    }

    public String getPassword() {
        return this.password;
    }
}
