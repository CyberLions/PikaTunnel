export default function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <img src="/logo.png" alt="Loading..." className="h-12 w-12 animate-bounce-slow rounded-xl" />
      <p className="text-sm text-stone-500 animate-pulse">Burrowing...</p>
    </div>
  );
}
