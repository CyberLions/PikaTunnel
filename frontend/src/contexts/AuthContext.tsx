import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";

interface User {
  sub: string;
  email: string | null;
  name: string | null;
  groups: string[];
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isAdmin: boolean;
  loading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function decodeJwtPayload(token: string): User | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return {
      sub: payload.sub || "",
      email: payload.email || null,
      name: payload.name || null,
      groups: payload.groups || [],
    };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const login = useCallback((newToken: string) => {
    localStorage.setItem("pikatunnel_token", newToken);
    setToken(newToken);
    const decoded = decodeJwtPayload(newToken);
    setUser(decoded);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("pikatunnel_token");
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem("pikatunnel_token");

    if (stored) {
      const decoded = decodeJwtPayload(stored);
      if (!decoded) {
        localStorage.removeItem("pikatunnel_token");
        setLoading(false);
        return;
      }
      setToken(stored);
      setUser(decoded);

      // Verify token is still valid
      fetch("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then((res) => {
          if (!res.ok) logout();
        })
        .catch(() => {})
        .finally(() => setLoading(false));
      return;
    }

    // No token — try dev mode (backend returns user without auth in dev)
    fetch("/api/v1/auth/me")
      .then((res) => {
        if (res.ok) return res.json();
        return null;
      })
      .then((data) => {
        if (data && data.sub) {
          setUser({
            sub: data.sub,
            email: data.email || null,
            name: data.name || null,
            groups: data.groups || [],
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [logout]);

  const isAdmin = user?.groups.includes("admin") ?? false;

  return (
    <AuthContext.Provider value={{ user, token, isAdmin, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
