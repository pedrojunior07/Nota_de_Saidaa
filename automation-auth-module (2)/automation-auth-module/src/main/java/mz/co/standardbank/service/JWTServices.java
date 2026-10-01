package mz.co.standardbank.service;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.Date;

import mz.co.standardbank.config.CustomPropertySourceFactory;
import mz.co.standardbank.entity.security.Account;
import mz.co.standardbank.exception.AuthenticationException;
import mz.co.standardbank.utils.HelperFactions;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.PropertySource;
import org.springframework.stereotype.Service;

@Service
@PropertySource(
        value = "classpath:auth.properties",
        factory = CustomPropertySourceFactory.class
)
public class JWTServices {

  private final EncryptionServices encryptionServices;

  @Value("${config.token.delimiter}")
  private String delimiter;

  @Value("${config.jwt.secret}")
  private String key;

  @Value("${config.jwt.validity}")
  private Integer validity;

  public JWTServices(EncryptionServices encryptionServices) {
    this.encryptionServices = encryptionServices;
  }

  public String generateJwtToken(Account account) throws RuntimeException, GeneralSecurityException, IOException {
    String groups = HelperFactions.listToStr(delimiter, account.getGroups());
    String dnTree = HelperFactions.listToStr(delimiter, account.getDnTree());
    String identifier = HelperFactions.getAlphaNumericString(10);
    String sid = encryptionServices.encrypt(identifier);

    return Jwts.builder()
        .setSubject("Authenticator")
        .setExpiration(new Date((new Date()).getTime() + (1000 * 60 * 60 * validity)))
        .claim("username", account.getUsername())
        .claim("firstName", account.getFirstName())
        .claim("lastName", account.getLastName())
        .claim("email", account.getEmail())
        .claim("groups", groups)
        .claim("dnTree", dnTree)
        // Add additional claims or information to the token if needed
        .signWith(SignatureAlgorithm.HS256, key)
        .compact();
  }

  public Account decodeAndVerifyJwt(String jwtToken) throws RuntimeException {
    try {
      Claims claims = Jwts.parser().setSigningKey(key).parseClaimsJws(jwtToken).getBody();
      if (claims != null) {
        Account account = new Account(claims, delimiter);
        return account;
      }
      throw new AuthenticationException();
    } catch (Exception e) {
      throw e;
    }
  }
}
