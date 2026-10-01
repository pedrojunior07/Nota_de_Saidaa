package mz.co.standardbank.service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import javax.crypto.Cipher;

import mz.co.standardbank.config.CustomPropertySourceFactory;
import mz.co.standardbank.service.configurations.KeysLoaderConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.PropertySource;
import org.springframework.security.crypto.codec.Base64;
import org.springframework.stereotype.Service;

@Service
@PropertySource(
        value = "classpath:auth.properties",
        factory = CustomPropertySourceFactory.class
)
public class EncryptionServices {

  private final KeysLoaderConfig keysLoaderConfig;

  @Value("${config.encrypton.keys-size}")
  private Integer keysSize;

  public EncryptionServices(KeysLoaderConfig keysLoaderConfig) {
    this.keysLoaderConfig = keysLoaderConfig;
  }

  public KeyPair generateKeyPair() throws NoSuchAlgorithmException {
    KeyPairGenerator keyPairGenerator = KeyPairGenerator.getInstance("RSA");
    keyPairGenerator.initialize(keysSize);
    return keyPairGenerator.generateKeyPair();
  }

  public String encrypt(String token) throws GeneralSecurityException, IOException, RuntimeException {

    PublicKey publicKey = keysLoaderConfig.getPublicKey();
    Cipher cipher = Cipher.getInstance("RSA");
    cipher.init(Cipher.ENCRYPT_MODE, publicKey);
    byte[] encryptedBytes = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
    return new String(Base64.encode(encryptedBytes), StandardCharsets.UTF_8);
  }

  public String decrypt(String encryptedToken) throws GeneralSecurityException, IOException, RuntimeException {

    PrivateKey privateKey = keysLoaderConfig.getPrivateKey();
    Cipher cipher = Cipher.getInstance("RSA");
    cipher.init(Cipher.DECRYPT_MODE, privateKey);
    byte[] decodedBytes = Base64.decode(encryptedToken.getBytes(StandardCharsets.UTF_8));
    byte[] decryptedBytes = cipher.doFinal(decodedBytes);
    return new String(decryptedBytes, StandardCharsets.UTF_8);
  }
}
