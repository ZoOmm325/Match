"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { usePathname } from "next/navigation";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled frontend error", error, info.componentStack);
  }

  private handleRetry = () => {
    this.setState({ hasError: false });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <main className="mx-auto flex min-h-screen w-full max-w-xl items-center px-4 py-12 sm:px-6">
          <div
            role="alert"
            className="w-full rounded-lg border border-red-200 bg-white p-6 text-center shadow-sm sm:p-8"
          >
            <p className="text-sm font-semibold text-red-700">页面出现异常</p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">暂时无法显示此页面</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              请刷新页面重试。如果问题持续出现，请稍后再访问。
            </p>
            <button
              type="button"
              onClick={this.handleRetry}
              className="mt-6 min-h-11 rounded-md bg-sky-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 focus-visible:ring-offset-2"
            >
              刷新页面
            </button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}

export default function RouteAwareErrorBoundary({ children }: ErrorBoundaryProps) {
  const pathname = usePathname();

  return <ErrorBoundary key={pathname}>{children}</ErrorBoundary>;
}
