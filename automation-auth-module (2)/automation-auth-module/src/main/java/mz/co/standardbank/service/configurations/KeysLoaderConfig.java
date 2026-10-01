package mz.co.standardbank.service.configurations;

import mz.co.standardbank.config.CustomPropertySourceFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;
import org.springframework.core.io.Resource;
import org.springframework.security.crypto.codec.Base64;
import org.springframework.util.FileCopyUtils;

import java.io.IOException;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;

@Configuration
@PropertySource(
        value = "classpath:auth.properties",
        factory = CustomPropertySourceFactory.class
)
public class KeysLoaderConfig {

    @Value("${config.public-key}")
    private Resource publicKeyResource;
    @Value("${config.private-key}")
    private Resource privateKeyResource;

    private String loadPemFile(Resource resource) throws IOException {
        byte[] fileBytes = FileCopyUtils.copyToByteArray(resource.getInputStream());
        return new String(fileBytes);
    }

    @Bean
    public PublicKey getPublicKey() throws GeneralSecurityException, IOException {
        String fileContent = this.loadPemFile(publicKeyResource);

        String key = fileContent
                .replace("-----BEGIN PUBLIC KEY-----", "")
                .replace("-----END PUBLIC KEY-----", "")
                .replaceAll("\\s", "");

        byte[] keyBytes = Base64.decode(key.getBytes());

        X509EncodedKeySpec keySpec = new X509EncodedKeySpec(keyBytes);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        return keyFactory.generatePublic(keySpec);
    }

    @Bean
    public PrivateKey getPrivateKey() throws GeneralSecurityException, IOException {
        String fileContent = loadPemFile(privateKeyResource);

        String key = fileContent
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");

        byte[] keyBytes = Base64.decode(key.getBytes());
        PKCS8EncodedKeySpec keySpec = new PKCS8EncodedKeySpec(keyBytes);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        return keyFactory.generatePrivate(keySpec);
    }
}
