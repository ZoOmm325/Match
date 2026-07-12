import type { Metadata } from "next";
import Link from "next/link";
import ErrorBoundary from "@/components/ui/ErrorBoundary";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "岗位专业匹配",
  description: "从招聘岗位描述中提取技能并匹配相关大学专业。",
};

const navItems = [
  { href: "/", label: "开始匹配" },
  { href: "/trends", label: "岗位趋势" },
  { href: "/history", label: "历史记录" },
  { href: "/majors", label: "专业浏览" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-slate-50 text-slate-950 antialiased">
        <ToastProvider>
          <ErrorBoundary>
            <div className="flex min-h-screen flex-col">
              <header className="border-b border-slate-200 bg-white">
                <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
                  <Link
                    href="/"
                    className="whitespace-nowrap text-lg font-semibold tracking-normal text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 focus-visible:ring-offset-2"
                  >
                    岗位专业匹配
                  </Link>
                  <nav
                    aria-label="主导航"
                    className="-mx-1 grid grid-cols-4 gap-1 overflow-x-auto px-1 sm:mx-0 sm:flex sm:w-auto sm:px-0"
                  >
                    {navItems.map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        className="min-h-10 whitespace-nowrap rounded-md px-2 py-2 text-center text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 sm:px-3"
                      >
                        {item.label}
                      </Link>
                    ))}
                  </nav>
                </div>
              </header>
              <main className="flex-1">{children}</main>
              <footer className="border-t border-slate-200 bg-white">
                <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-4 py-6 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
                  <p>岗位专业匹配</p>
                  <p>基于岗位技能与专业培养方向生成参考建议</p>
                </div>
              </footer>
            </div>
          </ErrorBoundary>
        </ToastProvider>
      </body>
    </html>
  );
}
