package mz.co.standardbank.spec;

import mz.co.standardbank.entity.enums.Activity;
import mz.co.standardbank.entity.enums.ActivityAction;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface LogActivity {
  Activity activity();

  ActivityAction action();
}
