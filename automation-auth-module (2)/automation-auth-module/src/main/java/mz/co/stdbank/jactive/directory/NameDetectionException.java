package mz.co.stdbank.jactive.directory;

public class NameDetectionException extends DomainException {
    public NameDetectionException(Throwable cause) {
        super("Failed to detect domain name automatically", cause);
    }
}
