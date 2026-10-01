package mz.co.standardbank.data;


import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.*;
import org.springframework.stereotype.Component;


@Data
@NoArgsConstructor
@AllArgsConstructor
@Component
public class UserCredentials {
    /**
     * Model to handle credential submission in other to authenticate the user
     */

    @NonNull
    private String username;

    @NonNull
    private String channel;

    @ToString.Exclude
    @NonNull
    private String password;

    @JsonIgnore
    private String traceId;
}
