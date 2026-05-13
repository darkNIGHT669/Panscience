"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { useAppStore } from "@/store/appStore";
import { getErrorMessage } from "@/lib/utils";
import { Eye, EyeOff, Loader2 } from "lucide-react";

const schema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});
type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const { setUser, setToken } = useAppStore();
  const [showPw, setShowPw] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      const token = await authApi.login(data.email, data.password);
      setToken(token);
      const { data: user } = await authApi.me();
      setUser(user);
      router.push("/chat");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="min-h-screen bg-surface flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-ink flex-col justify-between p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-5"
          style={{ backgroundImage: "radial-gradient(circle at 60% 40%, #E8612A 0%, transparent 60%)" }} />
        <div>
          <span className="font-display text-2xl font-bold text-white tracking-tight">
            Pan<span className="text-accent">Science</span>
          </span>
        </div>
        <div>
          <h1 className="font-display text-5xl font-bold text-white leading-[1.1] mb-6">
            Ask anything.<br />
            <span className="text-accent">Find everything.</span>
          </h1>
          <p className="text-white/50 text-lg font-body leading-relaxed max-w-sm">
            AI-powered Q&A across your PDFs, audio recordings, and video files — with precise citations and timestamps.
          </p>
        </div>
        <p className="text-white/20 text-sm font-mono">PanScience Innovations · AI Document Intelligence</p>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="mb-10">
            <h2 className="font-display text-3xl font-bold text-ink mb-2">Welcome back</h2>
            <p className="text-ink/50 font-body">Sign in to your workspace</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-ink/70 mb-1.5">Email</label>
              <input
                {...register("email")}
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full px-4 py-3 bg-white border border-surface-warm rounded-xl text-ink placeholder:text-ink/30
                  focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-all font-body"
              />
              {errors.email && (
                <p className="mt-1.5 text-xs text-red-500">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-ink/70 mb-1.5">Password</label>
              <div className="relative">
                <input
                  {...register("password")}
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="w-full px-4 py-3 bg-white border border-surface-warm rounded-xl text-ink placeholder:text-ink/30
                    focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-all font-body pr-11"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-ink/30 hover:text-ink/70 transition-colors"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1.5 text-xs text-red-500">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 bg-accent hover:bg-accent-hover text-white font-display font-semibold
                rounded-xl transition-all shadow-sm hover:shadow-md disabled:opacity-60 disabled:cursor-not-allowed
                flex items-center justify-center gap-2 text-sm tracking-wide"
            >
              {isSubmitting && <Loader2 size={16} className="animate-spin" />}
              Sign in
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-ink/40 font-body">
            No account?{" "}
            <Link href="/auth/register" className="text-accent hover:underline font-medium">
              Create one free
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
