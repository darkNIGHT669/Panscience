"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { Eye, EyeOff, Loader2 } from "lucide-react";

const schema = z.object({
  full_name: z.string().min(1, "Name is required").max(100),
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const [showPw, setShowPw] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await authApi.register(data.email, data.password, data.full_name);
      toast.success("Account created! Please sign in.");
      router.push("/auth/login");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-8">
      <div className="w-full max-w-sm animate-fade-up">
        <div className="mb-10">
          <Link href="/auth/login" className="font-display text-xl font-bold text-ink tracking-tight">
            Pan<span className="text-accent">Science</span>
          </Link>
          <h2 className="font-display text-3xl font-bold text-ink mt-8 mb-2">Create account</h2>
          <p className="text-ink/50">Start exploring your documents with AI</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {[
            { name: "full_name" as const, label: "Full name", type: "text", placeholder: "Ada Lovelace" },
            { name: "email" as const, label: "Email", type: "email", placeholder: "ada@example.com" },
          ].map(({ name, label, type, placeholder }) => (
            <div key={name}>
              <label className="block text-sm font-medium text-ink/70 mb-1.5">{label}</label>
              <input
                {...register(name)}
                type={type}
                placeholder={placeholder}
                className="w-full px-4 py-3 bg-white border border-surface-warm rounded-xl text-ink
                  placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent/40
                  focus:border-accent transition-all font-body"
              />
              {errors[name] && <p className="mt-1.5 text-xs text-red-500">{errors[name]?.message}</p>}
            </div>
          ))}

          <div>
            <label className="block text-sm font-medium text-ink/70 mb-1.5">Password</label>
            <div className="relative">
              <input
                {...register("password")}
                type={showPw ? "text" : "password"}
                placeholder="Min. 8 characters"
                className="w-full px-4 py-3 bg-white border border-surface-warm rounded-xl text-ink
                  placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent/40
                  focus:border-accent transition-all font-body pr-11"
              />
              <button
                type="button"
                onClick={() => setShowPw((v) => !v)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-ink/30 hover:text-ink/70 transition-colors"
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors.password && <p className="mt-1.5 text-xs text-red-500">{errors.password.message}</p>}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 bg-accent hover:bg-accent-hover text-white font-display font-semibold
              rounded-xl transition-all shadow-sm hover:shadow-md disabled:opacity-60 disabled:cursor-not-allowed
              flex items-center justify-center gap-2 text-sm tracking-wide"
          >
            {isSubmitting && <Loader2 size={16} className="animate-spin" />}
            Create account
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-ink/40">
          Already have an account?{" "}
          <Link href="/auth/login" className="text-accent hover:underline font-medium">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
