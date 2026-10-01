package mz.co.stdbank.jactive.directory;

public class ConnectionInfo {
    private int port;

    private String serverName;

    private ConnectionInfo() {}

    public boolean isPortSet() {
        return (this.port > 0);
    }

    public boolean isServerNameSet() {
        return (this.serverName != null);
    }

    public int getPort() {
        return this.port;
    }

    public String getServerName() {
        return this.serverName;
    }

    public static final class Builder {
        private ConnectionInfo info = null;

        public Builder() {
            this.info = new ConnectionInfo();
        }

        public Builder port(int port) {
            if (port < 1)
                throw new IllegalArgumentException("port number should be higher than 0");
            this.info.port = port;
            return this;
        }

        public Builder serverName(String name) {
            if (name == null || name.isEmpty())
                throw new IllegalArgumentException("server name must not be null nor empty");
            this.info.serverName = name;
            return this;
        }

        public ConnectionInfo build() {
            return this.info;
        }
    }
}
