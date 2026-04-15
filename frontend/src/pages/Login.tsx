import { useEffect, useState } from "react";
import { listProviders } from "../api/auth";
import type { OIDCProvider } from "../types";
import LoadingSpinner from "../components/LoadingSpinner";

export default function Login() {
  const [providers, setProviders] = useState<OIDCProvider[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await listProviders();
        setProviders(res.filter((p) => p.enabled));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-950">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-orange-600/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm">
        <div className="mb-8 text-center">
          <img
            src="/logo.png"
            alt="PikaTunnel"
            className="mx-auto mb-5 h-24 w-24 rounded-2xl shadow-2xl shadow-orange-500/20"
          />
          <h1 className="text-3xl font-bold">
            <span className="bg-gradient-to-r from-orange-400 to-orange-500 bg-clip-text text-transparent">Pika</span>
            <span className="text-stone-200">Tunnel</span>
          </h1>
          <p className="mt-2 text-sm text-stone-500">Sign in to start burrowing</p>
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : providers.length === 0 ? (
          <div className="card text-center">
            <p className="text-sm text-stone-500">No authentication providers configured.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {providers.map((provider) => (
              <a
                key={provider.id}
                href={`/api/v1/auth/login/${provider.id}`}
                className="flex w-full items-center justify-center gap-3 rounded-2xl border border-stone-700/30 bg-neutral-900/80 px-4 py-3.5 font-semibold text-stone-200 transition-all duration-200 hover:bg-stone-800/40 hover:border-orange-500/20 hover:shadow-lg hover:shadow-orange-500/5"
              >
                <svg className="h-5 w-5 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
                </svg>
                Sign in with {provider.name}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
