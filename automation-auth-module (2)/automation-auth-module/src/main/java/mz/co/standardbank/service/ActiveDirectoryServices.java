package mz.co.standardbank.service;

import static mz.co.standardbank.utils.HelperFactions.getSystemProperty;
import static mz.co.standardbank.utils.HelperFactions.getSystemPropertyAsInt;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import mz.co.standardbank.data.UserCredentials;
import mz.co.standardbank.exception.InvalidCredentialsExceptions;
import mz.co.stdbank.jactive.directory.*;
import org.jboss.logging.Logger;
import org.springframework.stereotype.Service;

@Service
public class ActiveDirectoryServices {

  private static final Logger log = Logger.getLogger(ActiveDirectoryServices.class);

  // Optional: fallback values or constants
  private static final int DEFAULT_PORT = 389;

  private boolean isServerReachable(String server, int port) {
    try (Socket socket = new Socket()) {
      socket.connect(new InetSocketAddress(server, port), 5000);
      return true;
    } catch (IOException e) {
      log.warnf("Server %s not reachable: %s", server, e.getMessage());
      return false;
    }
  }

  public User authenticate(UserCredentials userCredentials) throws RuntimeException {
    String mainDirectory = getSystemProperty("active.directory.server.main", null);
    String backupDirectory = getSystemProperty("active.directory.server.bkp", null);
    int port = getSystemPropertyAsInt("active.directory.port", DEFAULT_PORT);

    String directoryToUse = mainDirectory;
    Credentials credentials = Credentials.make(userCredentials.getUsername(), userCredentials.getPassword());
    Domain domain = new Domain();
    User user;
    if (mainDirectory != null && !mainDirectory.isEmpty()) {
      if (!isServerReachable(mainDirectory, port)) {
        log.warnf("Main directory not reachable, switching to backup directory.");
        directoryToUse = backupDirectory;
      }
      ConnectionInfo connectionInfo = new ConnectionInfo.Builder().port(port).serverName(directoryToUse).build();
      Session session = domain.getSession(credentials, connectionInfo);
      user = session.getUser();
    } else {
      ConnectionInfo connectionInfo = (new ConnectionInfo.Builder()).port(port).build();
      Session session = domain.getSession(credentials, connectionInfo);
      user = session.getUser();
    }

    if (user == null) throw new InvalidCredentialsExceptions();
    return user;
  }
}
