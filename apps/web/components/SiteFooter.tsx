import Link from "next/link";

import { ContactActions } from "@/components/ContactActions";

export function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-ink px-4 py-10 text-slate-300 sm:px-6">
      <div className="mx-auto grid max-w-[1280px] gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div>
          <Link href="/" className="text-sm font-semibold tracking-[0.22em] text-white">
            KAIQIANG.AI
          </Link>
          <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
            AI Avatar Generator for digital human videos, talking avatar workflows, and creator-ready AI video generation.
          </p>
          <div className="mt-5 flex flex-wrap gap-4 text-sm text-slate-400">
            <Link className="hover:text-white" href="/pricing">
              Pricing
            </Link>
            <Link className="hover:text-white" href="/studio/templates">
              Templates
            </Link>
            <Link className="hover:text-white" href="/studio/avatar">
              Avatar Studio
            </Link>
            <Link className="hover:text-white" href="/#contact">
              Contact
            </Link>
          </div>
        </div>
        <div>
          <h2 className="text-sm font-semibold text-white">Contact</h2>
          <div className="mt-4">
            <ContactActions tone="dark" compact />
          </div>
        </div>
      </div>
    </footer>
  );
}
