import { login } from './actions'
import { Button } from '@/components/ui/button'
import { ShieldAlert } from 'lucide-react'

export default async function LoginPage({ 
  searchParams 
}: { 
  searchParams: Promise<{ message?: string }> 
}) {
  const resolvedParams = await searchParams;
  
  return (
    <div className="flex flex-col w-full max-w-[400px] justify-center min-h-[70vh] mx-auto px-4">
      <div className="bg-card border border-border p-8 rounded-2xl shadow-xl">
        <div className="flex flex-col items-center mb-8 gap-2">
          <div className="bg-primary/10 p-3 rounded-full mb-2">
            <ShieldAlert className="h-6 w-6 text-primary" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Secure Dashboard</h1>
          <p className="text-muted-foreground text-sm text-center">Enter your administrator credentials to access the ServiPal bot controller.</p>
        </div>
        
        <form className="flex-1 flex flex-col w-full gap-4 text-foreground">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-semibold" htmlFor="email">
              Email Address
            </label>
            <input
              className="rounded-lg px-4 py-2.5 bg-secondary/20 border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-sm"
              name="email"
              type="email"
              placeholder="admin@servipal.com"
              required
            />
          </div>
          
          <div className="flex flex-col gap-1.5 mb-2">
            <label className="text-sm font-semibold" htmlFor="password">
              Password
            </label>
            <input
              className="rounded-lg px-4 py-2.5 bg-secondary/20 border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-sm"
              type="password"
              name="password"
              placeholder="••••••••"
              required
            />
          </div>
          
          <Button formAction={login} className="w-full font-semibold mt-2">
            Sign In
          </Button>
          
          {resolvedParams?.message && (
            <p className="mt-2 p-3 bg-red-50 text-red-700 font-medium text-center text-xs rounded-lg border border-red-100 animate-in fade-in zoom-in duration-300">
              {resolvedParams.message}
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
