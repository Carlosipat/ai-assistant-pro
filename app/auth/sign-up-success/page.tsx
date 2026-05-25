import Link from "next/link"
import { Mail, CheckCircle } from "lucide-react"

export default function SignUpSuccessPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8 text-center">
        {/* Success Icon */}
        <div className="flex justify-center">
          <div className="w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center">
            <CheckCircle className="h-10 w-10 text-green-500" />
          </div>
        </div>

        {/* Title */}
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-foreground">Check your email</h1>
          <p className="text-muted-foreground">
            {"We've sent you a confirmation link. Please check your email to verify your account."}
          </p>
        </div>

        {/* Email Icon Card */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-center gap-3 text-muted-foreground">
            <Mail className="h-5 w-5" />
            <span>Confirmation email sent</span>
          </div>
        </div>

        {/* Back to Login */}
        <Link
          href="/auth/login"
          className="inline-block w-full py-2.5 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 transition-all"
        >
          Back to login
        </Link>
      </div>
    </div>
  )
}
