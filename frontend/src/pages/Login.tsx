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
    <div className="flex min-h-screen items-center justify-center bg-slate-900">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Proxy Manager</h1>
          <p className="mt-2 text-sm text-slate-400">Sign in to continue</p>
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : providers.length === 0 ? (
          <p className="text-center text-sm text-slate-500">No authentication providers configured.</p>
        ) : (
          <div className="space-y-3">
            {providers.map((provider) => (
              <a
                key={provider.id}
                href={`/api/v1/auth/login/${provider.id}`}
                className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 font-medium text-slate-200 transition-colors hover:bg-slate-700"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
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
