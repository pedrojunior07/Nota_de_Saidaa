package mz.co.standardbank.holder;


import mz.co.standardbank.spec.CallerPrincipalHolder;
import mz.co.standardbank.spec.IAccount;

/**
 * CallerPrincipalHolder Implementation
 * Created by : Diogo Amaral - A251561
 * Test Automation Engineering
 * Standard Bank Mozambique
 * 2025
 */
public final class CallerPrincipalHolderImpl implements CallerPrincipalHolder {

    private static final ThreadLocal<IAccount> threadLocal = new ThreadLocal<>();

    @Override
    public IAccount getCurrentUser() {
        return threadLocal.get();
    }

    public static void setCurrentUser(IAccount principal) {
        threadLocal.set(principal);
    }

    public static void clear() {
        threadLocal.remove();
    }
}