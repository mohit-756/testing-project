import { useEffect, useState } from "react";
import { authApi } from "../services/api";
import { AuthContext } from "./auth-context";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refreshSession() {
    setLoading(true);
    setError("");
    try {
      const data = await authApi.me();
      setUser({
        id: data.user_id,
        role: data.role,
        name: data.name,
        email: data.email,
      });
      return data;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function login(credentials) {
    setError("");
    await authApi.login(credentials);
    await refreshSession();
  }

  async function signup(payload) {
    setError("");
    return authApi.signup(payload);
  }

  async function logout() {
    setError("");
    await authApi.logout();
    setUser(null);
  }

  useEffect(() => {
    refreshSession();
  }, []);

  const value = {
    user,
    loading,
    error,
    setError,
    login,
    signup,
    logout,
    refreshSession,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
