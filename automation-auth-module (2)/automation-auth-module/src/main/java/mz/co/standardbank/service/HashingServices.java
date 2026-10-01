package mz.co.standardbank.service;

import mz.co.standardbank.config.CustomPropertySourceFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.PropertySource;
import org.springframework.security.crypto.bcrypt.BCrypt;
import org.springframework.stereotype.Service;

@Service
@PropertySource(
        value = "classpath:auth.properties",
        factory = CustomPropertySourceFactory.class
)
public class HashingServices {

    @Value("${config.security.salt}")
    private Integer salt;
    public String hash(String message){
        String hashedMessage = BCrypt.hashpw(message, BCrypt.gensalt(salt));
        return hashedMessage;
    }

    public Boolean compare(String hashedStr, String str){
        Boolean isMatch = BCrypt.checkpw(str, hashedStr);
        return isMatch;
    }

}
